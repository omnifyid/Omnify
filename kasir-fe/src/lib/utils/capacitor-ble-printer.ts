import { BleClient } from '@capacitor-community/bluetooth-le';

const PROFILES = [
	{ service: '000018f0-0000-1000-8000-00805f9b34fb', characteristic: '00002af1-0000-1000-8000-00805f9b34fb' },
	{ service: '49535343-fe7d-4ae5-8fa9-9fafd205e455', characteristic: '49535343-8841-43f4-a8d4-ecbe34729bb3' },
	{ service: 'e7810a71-73ae-499d-8c15-faa9aef0c3f2', characteristic: 'bef8d6c9-9c21-4c9e-b632-bd58c1009f9f' },
];

const CHUNK = 512;
const CACHED_DEVICE_KEY = 'ble_printer_device_id';

let cachedDeviceId: string | null = null;

export async function printEscPosBleNative(data: Uint8Array): Promise<void> {
	await BleClient.initialize();

	const savedId = cachedDeviceId ?? localStorage.getItem(CACHED_DEVICE_KEY);
	if (savedId) {
		try {
			await doPrint(savedId, data);
			cachedDeviceId = savedId;
			return;
		} catch {
			cachedDeviceId = null;
			localStorage.removeItem(CACHED_DEVICE_KEY);
		}
	}

	const device = await BleClient.requestDevice({
		optionalServices: PROFILES.map((p) => p.service),
	});

	await doPrint(device.deviceId, data);
	cachedDeviceId = device.deviceId;
	localStorage.setItem(CACHED_DEVICE_KEY, device.deviceId);
}

async function doPrint(deviceId: string, data: Uint8Array): Promise<void> {
	await BleClient.connect(deviceId, () => {
		cachedDeviceId = null;
		localStorage.removeItem(CACHED_DEVICE_KEY);
	});

	try {
		const services = await BleClient.getServices(deviceId);
		const serviceUuids = services.map((s) => s.uuid.toLowerCase());

		const profile = PROFILES.find((p) => serviceUuids.includes(p.service.toLowerCase()));
		if (!profile) {
			throw new Error('Printer tidak didukung. Pastikan printer ESC/POS Bluetooth sudah terpasang.');
		}

		for (let i = 0; i < data.length; i += CHUNK) {
			const chunk = data.slice(i, i + CHUNK);
			await BleClient.writeWithoutResponse(
				deviceId,
				profile.service,
				profile.characteristic,
				new DataView(chunk.buffer, chunk.byteOffset, chunk.byteLength)
			);
		}
	} finally {
		await BleClient.disconnect(deviceId).catch(() => {});
	}
}
