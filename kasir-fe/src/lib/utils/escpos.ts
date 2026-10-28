import type { Order } from '$lib/api/types';
import { formatDateTime, formatRupiah } from '$lib/utils/format';

const ESC = 0x1b;
const GS = 0x1d;
const LF = 0x0a;
const WIDTH = 32;
// 58mm paper printable width at 203 DPI ≈ 384 dots = 48 bytes per row
const PAPER_PX = 384;

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

function sep(char = '-'): Uint8Array {
	return txt(char.repeat(WIDTH) + '\n');
}

function padLine(left: string, right: string): string {
	const maxLeft = WIDTH - right.length - 1;
	const l = left.length > maxLeft ? left.slice(0, maxLeft - 1) + '.' : left;
	return l + ' '.repeat(WIDTH - l.length - right.length) + right;
}

function snapshotLabel(snapshot: unknown[] | null | undefined): string {
	if (!snapshot?.length) return '';
	return snapshot
		.map((e) => {
			if (typeof e === 'string') return e;
			if (e && typeof e === 'object') {
				const r = e as Record<string, unknown>;
				return r.name ?? r.label ?? r.choice_name ?? r.item_name ?? '';
			}
			return '';
		})
		.filter(Boolean)
		.join(', ');
}

async function logoToRasterBytes(url: string): Promise<Uint8Array | null> {
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

export async function buildReceiptBytes(
	order: Order,
	storeName: string,
	cashPaid: number,
	opts?: { header?: string | null; footer?: string | null; logoUrl?: string | null }
): Promise<Uint8Array> {
	const parts: Uint8Array[] = [];
	const p = (...a: Uint8Array[]) => parts.push(...a);

	p(INIT());

	// Optional logo (raster bitmap, centered)
	if (opts?.logoUrl) {
		const logoBytes = await logoToRasterBytes(opts.logoUrl);
		if (logoBytes) {
			p(ALIGN(1), logoBytes, NL());
		}
	}

	// Store name, date, order#
	p(ALIGN(1), BOLD(true), txt(storeName + '\n'), BOLD(false));
	p(txt(formatDateTime(order.created_at) + '\n'));
	p(txt('#' + (order.order_number ?? order.id.slice(0, 8)) + '\n'));

	// Optional receipt header
	if (opts?.header?.trim()) {
		for (const line of opts.header.split('\n')) {
			p(txt(line + '\n'));
		}
	}

	p(ALIGN(0), sep());

	// Items
	for (const item of order.items ?? []) {
		const label = `${item.item_name_snapshot} x${item.quantity}`;
		const price = formatRupiah(item.line_total ?? 0);
		p(txt(padLine(label, price) + '\n'));

		const mods = [snapshotLabel(item.options_snapshot), snapshotLabel(item.addons_snapshot)]
			.filter(Boolean)
			.join(', ');
		if (mods) p(txt('  ' + mods + '\n'));

		if ((item.item_discount_amount ?? 0) > 0) {
			p(txt('  -' + formatRupiah(item.item_discount_amount!) + ' diskon\n'));
		}
	}

	p(sep());

	// Totals
	const itemDiscTotal = (order.items ?? []).reduce((s, i) => s + (i.item_discount_amount ?? 0), 0);
	const hasDiscount = (order.discount_amount ?? 0) > 0 || itemDiscTotal > 0;

	if (hasDiscount) {
		p(txt(padLine('Subtotal', formatRupiah(order.subtotal ?? 0)) + '\n'));
	}
	if (itemDiscTotal > 0) {
		p(txt(padLine('Item Discounts', '-' + formatRupiah(itemDiscTotal)) + '\n'));
	}
	if ((order.discount_amount ?? 0) > 0) {
		const label = order.discount_code_snapshot
			? `Diskon (${order.discount_code_snapshot})`
			: 'Diskon';
		p(txt(padLine(label, '-' + formatRupiah(order.discount_amount!)) + '\n'));
	}

	p(BOLD(true), txt(padLine('TOTAL', formatRupiah(order.total_amount)) + '\n'), BOLD(false));
	p(txt(padLine('Pembayaran', order.payment_method) + '\n'));

	if (cashPaid > 0) {
		p(txt(padLine('Tunai', formatRupiah(cashPaid)) + '\n'));
		p(txt(padLine('Kembali', formatRupiah(cashPaid - order.total_amount)) + '\n'));
	}

	p(sep());

	// Optional receipt footer, then thanks line
	if (opts?.footer?.trim()) {
		p(ALIGN(1));
		for (const line of opts.footer.split('\n')) {
			p(txt(line + '\n'));
		}
		p(ALIGN(0));
	} else {
		p(ALIGN(1), txt('Terima kasih!\n'), ALIGN(0));
	}

	p(FEED(3), CUT());

	return concat(...parts);
}
