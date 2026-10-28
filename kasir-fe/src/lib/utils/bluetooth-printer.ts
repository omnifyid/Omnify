import { Capacitor } from '@capacitor/core';
import { printEscPosBleNative } from './capacitor-ble-printer';

type GattProfile = { service: string; characteristic: string };

const PROFILES: GattProfile[] = [
	// Most common: generic ESC/POS Bluetooth printers (Epson-compatible, many Chinese brands)
	{ service: '000018f0-0000-1000-8000-00805f9b34fb', characteristic: '00002af1-0000-1000-8000-00805f9b34fb' },
	// BLE Serial Port Profile emulation
	{ service: '49535343-fe7d-4ae5-8fa9-9fafd205e455', characteristic: '49535343-8841-43f4-a8d4-ecbe34729bb3' },
	// Alternative profile used by some portable printers
	{ service: 'e7810a71-73ae-499d-8c15-faa9aef0c3f2', characteristic: 'bef8d6c9-9c21-4c9e-b632-bd58c1009f9f' },
];

const CHUNK = 512;

let cachedDevice: BluetoothDevice | null = null;
let cachedChar: BluetoothRemoteGATTCharacteristic | null = null;

async function getCharacteristic(): Promise<BluetoothRemoteGATTCharacteristic> {
	if (cachedDevice?.gatt?.connected && cachedChar) return cachedChar;

	let device: BluetoothDevice;
	try {
		device = await navigator.bluetooth.requestDevice({
			acceptAllDevices: true,
			optionalServices: PROFILES.map((p) => p.service),
		});
	} catch (err) {
		const msg = err instanceof Error ? err.message : String(err);
		if (msg.toLowerCase().includes('globally disabled') || msg.toLowerCase().includes('secure origin')) {
			throw new Error('Pastikan Bluetooth tidak diblokir');
		}
		// User cancelled the picker — rethrow as-is
		throw err;
	}

	const server = await device.gatt!.connect();

	for (const profile of PROFILES) {
		try {
			const service = await server.getPrimaryService(profile.service);
			const char = await service.getCharacteristic(profile.characteristic);
			cachedDevice = device;
			cachedChar = char;
			device.addEventListener('gattserverdisconnected', () => {
				cachedDevice = null;
				cachedChar = null;
			});
			return char;
		} catch {
			// try next profile
		}
	}

	throw new Error('Printer tidak didukung. Pastikan printer ESC/POS Bluetooth sudah terpasang.');
}

export function canPrint(): boolean {
	if (Capacitor.isNativePlatform()) return true;
	return typeof navigator !== 'undefined' && 'bluetooth' in navigator;
}

async function printEscPosBleWeb(data: Uint8Array): Promise<void> {
	if (typeof navigator === 'undefined' || !('bluetooth' in navigator)) {
		throw new Error('Web Bluetooth tidak tersedia. Gunakan Chrome di Android atau desktop.');
	}

	const char = await getCharacteristic();

	for (let i = 0; i < data.length; i += CHUNK) {
		await char.writeValueWithoutResponse(data.slice(i, i + CHUNK));
	}
}

export async function printEscPos(data: Uint8Array): Promise<void> {
	if (Capacitor.isNativePlatform()) {
		return printEscPosBleNative(data);
	}
	return printEscPosBleWeb(data);
}
