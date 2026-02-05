/**
 * Scanner Service - Global Bluetooth OBD scanner management
 * 
 * This store manages the Bluetooth connection to the OBD2 scanner.
 * The AI can request data via WebSocket, and this service responds.
 */

// Web Bluetooth API type declarations (not in standard TypeScript libs)
declare global {
	interface Navigator {
		bluetooth: Bluetooth;
	}
	interface Bluetooth {
		requestDevice(options: RequestDeviceOptions): Promise<BluetoothDevice>;
	}
	interface RequestDeviceOptions {
		filters?: BluetoothLEScanFilter[];
		optionalServices?: BluetoothServiceUUID[];
		acceptAllDevices?: boolean;
	}
	interface BluetoothLEScanFilter {
		services?: BluetoothServiceUUID[];
		name?: string;
		namePrefix?: string;
	}
	type BluetoothServiceUUID = string | number;
	interface BluetoothDevice extends EventTarget {
		id: string;
		name?: string;
		gatt?: BluetoothRemoteGATTServer;
	}
	interface BluetoothRemoteGATTServer {
		device: BluetoothDevice;
		connected: boolean;
		connect(): Promise<BluetoothRemoteGATTServer>;
		disconnect(): void;
		getPrimaryService(service: BluetoothServiceUUID): Promise<BluetoothRemoteGATTService>;
	}
	interface BluetoothRemoteGATTService {
		device: BluetoothDevice;
		uuid: string;
		getCharacteristic(characteristic: BluetoothServiceUUID): Promise<BluetoothRemoteGATTCharacteristic>;
	}
	interface BluetoothRemoteGATTCharacteristic extends EventTarget {
		service: BluetoothRemoteGATTService;
		uuid: string;
		value?: DataView;
		startNotifications(): Promise<BluetoothRemoteGATTCharacteristic>;
		stopNotifications(): Promise<BluetoothRemoteGATTCharacteristic>;
		readValue(): Promise<DataView>;
		writeValue(value: BufferSource): Promise<void>;
	}
}

import { writable, get } from 'svelte/store';
import { WEBUI_API_BASE_URL } from '$lib/constants';

// Connection state
export const scannerConnected = writable(false);
export const scannerConnecting = writable(false);
export const scannerDevice = writable<BluetoothDevice | null>(null);
export const scannerError = writable<string | null>(null);

// Cached data from last read
export const scannerVIN = writable<string>('');
export const scannerDTCs = writable<Array<{ code: string; status: string }>>([]);
export const scannerPIDs = writable<Record<string, number>>({});

// Internal state
let characteristic: BluetoothRemoteGATTCharacteristic | null = null;
let responseBuffer = '';
let responseResolve: ((value: string) => void) | null = null;

// PID decoders
const pidDecoders: Record<string, { name: string; decode: (d: number[]) => number }> = {
	'04': { name: 'engine_load', decode: (d) => d[0] / 2.55 },
	'05': { name: 'coolant_temp', decode: (d) => d[0] - 40 },
	'06': { name: 'stft1', decode: (d) => (d[0] - 128) * 100 / 128 },
	'07': { name: 'ltft1', decode: (d) => (d[0] - 128) * 100 / 128 },
	'08': { name: 'stft2', decode: (d) => (d[0] - 128) * 100 / 128 },
	'09': { name: 'ltft2', decode: (d) => (d[0] - 128) * 100 / 128 },
	'0C': { name: 'rpm', decode: (d) => ((d[0] * 256) + d[1]) / 4 },
	'0D': { name: 'speed_kmh', decode: (d) => d[0] },
	'0F': { name: 'intake_air_temp', decode: (d) => d[0] - 40 },
	'10': { name: 'maf', decode: (d) => ((d[0] * 256) + d[1]) / 100 },
	'11': { name: 'throttle', decode: (d) => d[0] / 2.55 },
	'42': { name: 'control_voltage', decode: (d) => ((d[0] * 256) + d[1]) / 1000 },
	'2F': { name: 'fuel_level', decode: (d) => d[0] / 2.55 },
};

// Check if Web Bluetooth is supported
export function isBluetoothSupported(): boolean {
	return typeof navigator !== 'undefined' && 'bluetooth' in navigator;
}

// Connect to OBD scanner
export async function connectScanner(): Promise<boolean> {
	if (!isBluetoothSupported()) {
		scannerError.set('Web Bluetooth not supported. Use Chrome on Android.');
		return false;
	}

	scannerConnecting.set(true);
	scannerError.set(null);

	try {
		// Request Bluetooth device
		const device = await navigator.bluetooth.requestDevice({
			filters: [
				{ namePrefix: 'OBDLink' },
				{ namePrefix: 'OBDII' },
				{ namePrefix: 'ELM' },
				{ namePrefix: 'Vgate' },
				{ namePrefix: 'Veepeak' },
			],
			optionalServices: ['0000ffe0-0000-1000-8000-00805f9b34fb']
		});

		scannerDevice.set(device);

		// Connect to GATT server
		const server = await device.gatt!.connect();
		
		// Get service and characteristic
		const service = await server.getPrimaryService('0000ffe0-0000-1000-8000-00805f9b34fb');
		characteristic = await service.getCharacteristic('0000ffe1-0000-1000-8000-00805f9b34fb');

		// Subscribe to notifications
		await characteristic.startNotifications();
		characteristic.addEventListener('characteristicvaluechanged', handleNotification);

		// Handle disconnect
		device.addEventListener('gattserverdisconnected', () => {
			scannerConnected.set(false);
			scannerDevice.set(null);
			characteristic = null;
		});

		// Initialize ELM327
		await initializeAdapter();

		scannerConnected.set(true);
		scannerConnecting.set(false);
		return true;

	} catch (error: any) {
		scannerError.set(error.message || 'Failed to connect');
		scannerConnecting.set(false);
		return false;
	}
}

// Disconnect scanner
export function disconnectScanner(): void {
	const device = get(scannerDevice);
	if (device?.gatt?.connected) {
		device.gatt.disconnect();
	}
	scannerConnected.set(false);
	scannerDevice.set(null);
	characteristic = null;
}

// Handle incoming data from scanner
function handleNotification(event: Event): void {
	const target = event.target as BluetoothRemoteGATTCharacteristic;
	const value = target.value;
	if (!value) return;

	const decoder = new TextDecoder();
	const chunk = decoder.decode(value);
	responseBuffer += chunk;

	// Check for prompt (end of response)
	if (responseBuffer.includes('>')) {
		const response = responseBuffer.replace(/>/g, '').trim();
		responseBuffer = '';
		if (responseResolve) {
			responseResolve(response);
			responseResolve = null;
		}
	}
}

// Send command and wait for response
async function sendCommand(cmd: string, timeout: number = 3000): Promise<string> {
	if (!characteristic) throw new Error('Not connected');

	responseBuffer = '';
	
	const promise = new Promise<string>((resolve, reject) => {
		responseResolve = resolve;
		setTimeout(() => {
			if (responseResolve) {
				responseResolve = null;
				reject(new Error('Timeout'));
			}
		}, timeout);
	});

	const encoder = new TextEncoder();
	await characteristic.writeValue(encoder.encode(cmd + '\r'));

	return promise;
}

// Initialize ELM327 adapter
async function initializeAdapter(): Promise<void> {
	await sendCommand('ATZ', 5000);  // Reset
	await new Promise(r => setTimeout(r, 1000));
	await sendCommand('ATE0');  // Echo off
	await sendCommand('ATL0');  // Linefeeds off
	await sendCommand('ATS0');  // Spaces off
	await sendCommand('ATH0');  // Headers off
	await sendCommand('ATSP0'); // Auto protocol
}

// Read VIN
export async function readVIN(): Promise<string> {
	try {
		const response = await sendCommand('0902', 5000);
		const vin = parseVIN(response);
		scannerVIN.set(vin);
		return vin;
	} catch {
		return '';
	}
}

function parseVIN(response: string): string {
	// VIN response format varies, extract ASCII characters
	const lines = response.split('\n').filter(l => l.trim());
	let bytes: number[] = [];
	
	for (const line of lines) {
		const cleaned = line.replace(/[^0-9A-Fa-f]/g, '');
		// Skip header bytes (49 02 XX)
		let start = 0;
		if (cleaned.startsWith('4902')) start = 6;
		
		for (let i = start; i < cleaned.length; i += 2) {
			const byte = parseInt(cleaned.substring(i, i + 2), 16);
			if (byte >= 32 && byte <= 126) bytes.push(byte);
		}
	}
	
	return String.fromCharCode(...bytes).substring(0, 17);
}

// Read DTCs
export async function readDTCs(): Promise<Array<{ code: string; status: string }>> {
	const dtcs: Array<{ code: string; status: string }> = [];
	
	try {
		// Read stored codes (Mode 03)
		const stored = await sendCommand('03', 5000);
		dtcs.push(...parseDTCs(stored, 'stored'));
		
		// Read pending codes (Mode 07)
		const pending = await sendCommand('07', 5000);
		dtcs.push(...parseDTCs(pending, 'pending'));
		
		scannerDTCs.set(dtcs);
		return dtcs;
	} catch {
		return [];
	}
}

function parseDTCs(response: string, status: string): Array<{ code: string; status: string }> {
	const dtcs: Array<{ code: string; status: string }> = [];
	const cleaned = response.replace(/[^0-9A-Fa-f]/g, '');
	
	// Skip mode response byte (43 or 47)
	let data = cleaned;
	if (data.startsWith('43') || data.startsWith('47')) {
		data = data.substring(2);
	}
	
	// Parse DTC pairs (4 hex chars each)
	for (let i = 0; i + 4 <= data.length; i += 4) {
		const dtcHex = data.substring(i, i + 4);
		const code = decodeDTC(dtcHex);
		if (code && code !== 'P0000') {
			dtcs.push({ code, status });
		}
	}
	
	return dtcs;
}

function decodeDTC(hex: string): string | null {
	if (hex.length !== 4) return null;
	
	const firstByte = parseInt(hex.substring(0, 2), 16);
	const secondByte = parseInt(hex.substring(2, 4), 16);
	
	const typeMap: Record<number, string> = {
		0: 'P0', 1: 'P1', 2: 'P2', 3: 'P3',
		4: 'C0', 5: 'C1', 6: 'C2', 7: 'C3',
		8: 'B0', 9: 'B1', 10: 'B2', 11: 'B3',
		12: 'U0', 13: 'U1', 14: 'U2', 15: 'U3'
	};
	
	const firstNibble = (firstByte >> 4) & 0x0F;
	const prefix = typeMap[firstNibble] || 'P0';
	const thirdChar = (firstByte & 0x0F).toString(16).toUpperCase();
	const lastTwo = secondByte.toString(16).toUpperCase().padStart(2, '0');
	
	return `${prefix}${thirdChar}${lastTwo}`;
}

// Read common PIDs
export async function readPIDs(): Promise<Record<string, number>> {
	const pids: Record<string, number> = {};
	
	// Read supported PIDs first
	const pidsToRead = ['04', '05', '06', '07', '0C', '0D', '11', '42'];
	
	for (const pid of pidsToRead) {
		try {
			const response = await sendCommand(`01${pid}`, 2000);
			const value = parsePIDResponse(response, pid);
			if (value !== null) {
				const decoder = pidDecoders[pid];
				if (decoder) {
					pids[decoder.name] = value;
				}
			}
		} catch {
			// Skip failed PIDs
		}
	}
	
	scannerPIDs.set(pids);
	return pids;
}

function parsePIDResponse(response: string, pid: string): number | null {
	const cleaned = response.replace(/[^0-9A-Fa-f]/g, '');
	
	// Response format: 41 XX YY [ZZ] - skip 41 and PID
	if (!cleaned.startsWith('41')) return null;
	
	const data = cleaned.substring(4); // Skip 41 XX
	const decoder = pidDecoders[pid];
	if (!decoder) return null;
	
	const bytes: number[] = [];
	for (let i = 0; i < data.length && bytes.length < 4; i += 2) {
		bytes.push(parseInt(data.substring(i, i + 2), 16));
	}
	
	if (bytes.length === 0) return null;
	return decoder.decode(bytes);
}

// Full scan - reads everything and returns structured data
export async function performFullScan(): Promise<{
	vin: string;
	dtcs: Array<{ code: string; status: string }>;
	pids: Record<string, number>;
}> {
	const vin = await readVIN();
	const dtcs = await readDTCs();
	const pids = await readPIDs();
	
	return { vin, dtcs, pids };
}

// Clear DTCs
export async function clearDTCs(): Promise<boolean> {
	try {
		await sendCommand('04', 3000);
		scannerDTCs.set([]);
		return true;
	} catch {
		return false;
	}
}
