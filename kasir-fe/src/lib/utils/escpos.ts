import type { Order, Store } from '$lib/api/types';
import {
	customerReceipt,
	kitchenTicket,
	paperChars,
	receiptOptions,
	type ReceiptLine,
	type ReceiptOptions
} from '$lib/utils/receipt';

const ESC = 0x1b;
const GS = 0x1d;
const LF = 0x0a;
// printable dots per row at 203 DPI: 384 on 58 mm paper, 576 on 80 mm
const paperPx = (paper: '58' | '80') => (paper === '80' ? 576 : 384);

function cmd(...bytes: number[]): Uint8Array {
	return new Uint8Array(bytes);
}

function txt(str: string): Uint8Array {
	return new TextEncoder().encode(str);
}

function concat(...parts: Uint8Array[]): Uint8Array {
	const total = parts.reduce((sum, p) => sum + p.length, 0);
	const out = new Uint8Array(total);
	let off = 0;
	for (const p of parts) { out.set(p, off); off += p.length; }
	return out;
}

const INIT   = () => cmd(ESC, 0x40);
const ALIGN  = (n: 0 | 1 | 2) => cmd(ESC, 0x61, n);
const BOLD   = (on: boolean) => cmd(ESC, 0x45, on ? 1 : 0);
const FEED   = (n: number) => cmd(ESC, 0x64, n);
const CUT    = () => cmd(GS, 0x56, 0x42, 0x00);
const NL     = () => new Uint8Array([LF]);

function padLine(left: string, right: string, width: number): string {
	const maxLeft = Math.max(1, width - right.length - 1);
	const l = left.length > maxLeft ? left.slice(0, maxLeft - 1) + '.' : left;
	return l + ' '.repeat(Math.max(1, width - l.length - right.length)) + right;
}

/** Wraps on spaces so long header/footer lines do not run off the paper. */
function wrapText(text: string, width: number): string[] {
	const out: string[] = [];
	for (const raw of text.split('\n')) {
		let line = '';
		for (const word of raw.split(' ')) {
			const next = line ? `${line} ${word}` : word;
			if (next.length <= width) line = next;
			else {
				if (line) out.push(line);
				line = word;
				while (line.length > width) { out.push(line.slice(0, width)); line = line.slice(width); }
			}
		}
		out.push(line);
	}
	return out;
}

async function logoToRasterBytes(url: string, PAPER_PX: number): Promise<Uint8Array | null> {
	try {
		const resp = await fetch(url);
		if (!resp.ok) return null;
		const blob = await resp.blob();
		const bmp = await createImageBitmap(blob);

		// Scale to fit paper width, cap height at 200px to avoid massive logos
		const scale = Math.min(1, PAPER_PX / bmp.width, 200 / bmp.height);
		const w = Math.round(bmp.width * scale);
		const h = Math.round(bmp.height * scale);

		// Draw centered on full paper-width canvas with white background
		const canvas = new OffscreenCanvas(PAPER_PX, h);
		const ctx = canvas.getContext('2d')!;
		ctx.fillStyle = 'white';
		ctx.fillRect(0, 0, PAPER_PX, h);
		const xOffset = Math.floor((PAPER_PX - w) / 2);
		ctx.drawImage(bmp, xOffset, 0, w, h);

		const imgData = ctx.getImageData(0, 0, PAPER_PX, h);
		const { data } = imgData;

		// Convert to 1-bit monochrome (luminance threshold 128)
		const bytesPerRow = PAPER_PX / 8; // 48
		const bitmap = new Uint8Array(bytesPerRow * h);
		for (let y = 0; y < h; y++) {
			for (let x = 0; x < PAPER_PX; x++) {
				const idx = (y * PAPER_PX + x) * 4;
				const lum = (data[idx] * 299 + data[idx + 1] * 587 + data[idx + 2] * 114) / 1000;
				if (lum < 128) {
					bitmap[y * bytesPerRow + (x >> 3)] |= 0x80 >> (x & 7);
				}
			}
		}

		// GS v 0 raster command: 1D 76 30 m xL xH yL yH [data]
		const xL = bytesPerRow & 0xff;
		const xH = (bytesPerRow >> 8) & 0xff;
		const yL = h & 0xff;
		const yH = (h >> 8) & 0xff;
		const header = new Uint8Array([GS, 0x76, 0x30, 0x00, xL, xH, yL, yH]);
		return concat(header, bitmap);
	} catch {
		return null;
	}
}

const DOUBLE = (on: boolean) => cmd(GS, 0x21, on ? 0x11 : 0x00);

/** Encodes a receipt document for an ESC/POS printer. */
async function encodeDoc(lines: ReceiptLine[], o: ReceiptOptions): Promise<Uint8Array> {
	const width = paperChars(o);
	const parts: Uint8Array[] = [INIT()];
	const p = (...a: Uint8Array[]) => parts.push(...a);

	for (const line of lines) {
		if (line.t === 'logo') {
			const bytes = await logoToRasterBytes(line.url, paperPx(o.paper));
			if (bytes) p(ALIGN(1), bytes, NL(), ALIGN(0));
		} else if (line.t === 'rule') {
			p(ALIGN(0), txt('-'.repeat(width) + '\n'));
		} else if (line.t === 'text') {
			const w = line.big ? Math.floor(width / 2) : width - (line.indent ? 2 : 0);
			p(ALIGN(line.align === 'center' ? 1 : 0), BOLD(!!line.bold), DOUBLE(!!line.big));
			for (const l of wrapText(line.text, w)) p(txt((line.indent ? '  ' : '') + l + '\n'));
			p(DOUBLE(false), BOLD(false), ALIGN(0));
		} else {
			const w = line.big ? Math.floor(width / 2) : width;
			p(ALIGN(0), BOLD(!!line.bold), DOUBLE(!!line.big), txt(padLine(line.left, line.right, w) + '\n'), DOUBLE(false), BOLD(false));
		}
	}
	p(FEED(3), CUT());
	return concat(...parts);
}

type StoreForPrint = Pick<
	Store,
	'name' | 'logo_url' | 'show_logo' | 'address' | 'phone' | 'receipt_header' | 'receipt_footer' | 'receipt_options'
>;

/** Customer receipt. `cashPaid` is only a fallback for orders that did not store the cash received. */
export function buildReceiptBytes(order: Order, store: StoreForPrint, cashPaid = 0): Promise<Uint8Array> {
	const o = receiptOptions(store);
	return encodeDoc(customerReceipt(order, store, o, cashPaid), o);
}

/** Kitchen ticket: big order number, quantities and modifiers, no prices. */
export function buildKitchenTicketBytes(order: Order, store: StoreForPrint): Promise<Uint8Array> {
	const o = receiptOptions(store);
	return encodeDoc(kitchenTicket(order, store, o), o);
}
