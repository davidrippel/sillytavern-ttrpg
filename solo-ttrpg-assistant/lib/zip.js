const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();

function makeCrcTable() {
    const table = new Uint32Array(256);

    for (let i = 0; i < 256; i += 1) {
        let c = i;

        for (let j = 0; j < 8; j += 1) {
            c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
        }

        table[i] = c >>> 0;
    }

    return table;
}

const CRC_TABLE = makeCrcTable();

function crc32(bytes) {
    let crc = 0xffffffff;

    for (const byte of bytes) {
        crc = CRC_TABLE[(crc ^ byte) & 0xff] ^ (crc >>> 8);
    }

    return (crc ^ 0xffffffff) >>> 0;
}

function dosDateTime(date) {
    const safe = new Date(date);
    const year = Math.max(1980, safe.getFullYear());
    const dosTime = ((safe.getHours() & 0x1f) << 11)
        | ((safe.getMinutes() & 0x3f) << 5)
        | ((Math.floor(safe.getSeconds() / 2)) & 0x1f);
    const dosDate = (((year - 1980) & 0x7f) << 9)
        | (((safe.getMonth() + 1) & 0x0f) << 5)
        | (safe.getDate() & 0x1f);

    return { dosTime, dosDate };
}

function concatUint8Arrays(parts) {
    const total = parts.reduce((sum, part) => sum + part.length, 0);
    const out = new Uint8Array(total);
    let offset = 0;

    for (const part of parts) {
        out.set(part, offset);
        offset += part.length;
    }

    return out;
}

function writeUint16(view, offset, value) {
    view.setUint16(offset, value, true);
}

function writeUint32(view, offset, value) {
    view.setUint32(offset, value >>> 0, true);
}

export function stringToBytes(text) {
    return textEncoder.encode(text);
}

export function bytesToString(bytes) {
    return textDecoder.decode(bytes);
}

export function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function createZip(entries) {
    const localParts = [];
    const centralParts = [];
    let offset = 0;
    const createdAt = new Date();
    const { dosTime, dosDate } = dosDateTime(createdAt);

    for (const entry of entries) {
        const filenameBytes = stringToBytes(entry.name);
        const dataBytes = typeof entry.data === 'string' ? stringToBytes(entry.data) : entry.data;
        const checksum = crc32(dataBytes);

        const localHeader = new Uint8Array(30 + filenameBytes.length);
        const localView = new DataView(localHeader.buffer);
        writeUint32(localView, 0, 0x04034b50);
        writeUint16(localView, 4, 20);
        writeUint16(localView, 6, 0);
        writeUint16(localView, 8, 0);
        writeUint16(localView, 10, dosTime);
        writeUint16(localView, 12, dosDate);
        writeUint32(localView, 14, checksum);
        writeUint32(localView, 18, dataBytes.length);
        writeUint32(localView, 22, dataBytes.length);
        writeUint16(localView, 26, filenameBytes.length);
        writeUint16(localView, 28, 0);
        localHeader.set(filenameBytes, 30);
        localParts.push(localHeader, dataBytes);

        const centralHeader = new Uint8Array(46 + filenameBytes.length);
        const centralView = new DataView(centralHeader.buffer);
        writeUint32(centralView, 0, 0x02014b50);
        writeUint16(centralView, 4, 20);
        writeUint16(centralView, 6, 20);
        writeUint16(centralView, 8, 0);
        writeUint16(centralView, 10, 0);
        writeUint16(centralView, 12, dosTime);
        writeUint16(centralView, 14, dosDate);
        writeUint32(centralView, 16, checksum);
        writeUint32(centralView, 20, dataBytes.length);
        writeUint32(centralView, 24, dataBytes.length);
        writeUint16(centralView, 28, filenameBytes.length);
        writeUint16(centralView, 30, 0);
        writeUint16(centralView, 32, 0);
        writeUint16(centralView, 34, 0);
        writeUint16(centralView, 36, 0);
        writeUint32(centralView, 38, 0);
        writeUint32(centralView, 42, offset);
        centralHeader.set(filenameBytes, 46);
        centralParts.push(centralHeader);

        offset += localHeader.length + dataBytes.length;
    }

    const centralDirectory = concatUint8Arrays(centralParts);
    const endRecord = new Uint8Array(22);
    const endView = new DataView(endRecord.buffer);
    writeUint32(endView, 0, 0x06054b50);
    writeUint16(endView, 4, 0);
    writeUint16(endView, 6, 0);
    writeUint16(endView, 8, entries.length);
    writeUint16(endView, 10, entries.length);
    writeUint32(endView, 12, centralDirectory.length);
    writeUint32(endView, 16, offset);
    writeUint16(endView, 20, 0);

    return new Blob([concatUint8Arrays([...localParts, centralDirectory, endRecord])], { type: 'application/zip' });
}

export async function readZip(file) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    const entries = new Map();
    let offset = 0;

    while (offset + 4 <= bytes.length) {
        const view = new DataView(bytes.buffer, bytes.byteOffset + offset);
        const signature = view.getUint32(0, true);

        if (signature !== 0x04034b50) {
            break;
        }

        const compressionMethod = view.getUint16(8, true);
        const compressedSize = view.getUint32(18, true);
        const uncompressedSize = view.getUint32(22, true);
        const nameLength = view.getUint16(26, true);
        const extraLength = view.getUint16(28, true);

        if (compressionMethod !== 0) {
            throw new Error('Only store-only ZIP bundles are supported.');
        }

        const nameStart = offset + 30;
        const nameEnd = nameStart + nameLength;
        const dataStart = nameEnd + extraLength;
        const dataEnd = dataStart + compressedSize;

        const name = bytesToString(bytes.slice(nameStart, nameEnd));
        const data = bytes.slice(dataStart, dataEnd);
        if (data.length !== uncompressedSize) {
            throw new Error(`ZIP entry size mismatch for ${name}.`);
        }

        entries.set(name, data);
        offset = dataEnd;
    }

    return entries;
}
