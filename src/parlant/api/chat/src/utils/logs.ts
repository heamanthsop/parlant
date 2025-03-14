/* eslint-disable no-useless-escape */
import {Log} from './interfaces';

const logLevels = ['WARNING', 'INFO', 'DEBUG'];
const DB_NAME = 'Parlant';
const STORE_NAME = 'logs';

/**
 * Calculate the size of a specific IndexedDB table/object store in megabytes
 * @param {string} databaseName - The name of the IndexedDB database
 * @param {string} tableName - The name of the table/object store to measure
 * @returns {Promise<number>} - Size in megabytes
 */
export function getIndexedDBSize(databaseName = DB_NAME, tableName = STORE_NAME): Promise<number> {
	return new Promise((resolve, reject) => {
		const request = indexedDB.open(databaseName);

		request.onerror = (event) => {
			const target = event?.target as IDBOpenDBRequest;
			const error = target?.error;
			reject(new Error(`Failed to open database: ${error}`));
		};

		request.onsuccess = (event) => {
			const target = event?.target as IDBOpenDBRequest;
			const db = target?.result;

			if (!db.objectStoreNames.contains(tableName)) {
				db.close();
				reject(new Error(`Table "${tableName}" does not exist in database "${databaseName}"`));
				return;
			}

			const transaction = db.transaction(tableName, 'readonly');
			const store = transaction.objectStore(tableName);

			const getAllRequest = store.getAll();

			getAllRequest.onerror = (event: Event) => {
				db.close();
				const target = event.target as IDBRequest;
				reject(new Error(`Failed to read data: ${target.error}`));
			};

			getAllRequest.onsuccess = (event: Event) => {
				const target = event.target as IDBRequest;
				const records = target.result;
				let totalSize = 0;

				records.forEach((record: Record<string, unknown>) => {
					const serialized = JSON.stringify(record);
					totalSize += serialized.length * 2;
				});

				const sizeInMB = totalSize / (1024 * 1024);

				db.close();
				resolve(sizeInMB);
			};
		};
	});
}

export function clearIndexedDBData(dbName = DB_NAME, objectStoreName = STORE_NAME) {
	return new Promise((resolve, reject) => {
		const request = indexedDB.open(dbName);

		request.onerror = (event) => {
			const target = event?.target as IDBOpenDBRequest;
			const error = target?.error;
			reject(error);
		};

		request.onsuccess = (event) => {
			const target = event?.target as IDBOpenDBRequest;
			const db = target?.result;
			const transaction = db.transaction(objectStoreName, 'readwrite');
			const objectStore = transaction.objectStore(objectStoreName);
			const clearRequest = objectStore.clear();

			clearRequest.onsuccess = () => {
				resolve(null);
			};

			clearRequest.onerror = (clearEvent: Event) => {
				const target = clearEvent.target as IDBRequest;
				reject(target.error);
			};

			transaction.oncomplete = () => {
				db.close();
			};
		};
	});
}

function openDB() {
	return new Promise<IDBDatabase>((resolve, reject) => {
		const request = indexedDB.open(DB_NAME, 1);
		request.onupgradeneeded = () => {
			const db = request.result;
			if (!db.objectStoreNames.contains(STORE_NAME)) {
				db.createObjectStore(STORE_NAME, {autoIncrement: true});
			}
		};
		request.onsuccess = () => resolve(request.result);
		request.onerror = () => reject(request.error);
	});
}

async function getLogs(correlation_id: string): Promise<Log[]> {
	const db = await openDB();
	return new Promise((resolve, reject) => {
		const transaction = db.transaction(STORE_NAME, 'readonly');
		const store = transaction.objectStore(STORE_NAME);
		const count = store.count();
		count.onsuccess = () => console.log('record count', count.result);
		const request = store.get(correlation_id);
		request.onsuccess = () => resolve(request.result || []);
		request.onerror = () => reject(request.error);
	});
}

export const handleChatLogs = async (log: Log) => {
	const db = await openDB();
	const transaction = db.transaction(STORE_NAME, 'readwrite');
	const store = transaction.objectStore(STORE_NAME);

	const logEntry = store.get(log.correlation_id);

	logEntry.onsuccess = () => {
		const data = logEntry.result;
		if (!data) {
			store.put([log], log.correlation_id);
		} else {
			data.push(log);
			store.put(data, log.correlation_id);
		}
	};
	logEntry.onerror = () => console.error(logEntry.error);
};

export const getMessageLogs = async (correlation_id: string): Promise<Log[]> => {
	return getLogs(correlation_id);
};

export const getMessageLogsWithFilters = async (correlation_id: string, filters: {level: string; types?: string[]; content?: string[]}): Promise<Log[]> => {
	const logs = await getMessageLogs(correlation_id);
	const escapedWords = filters?.content?.map((word) => word.replace(/([.*+?^=!:${}()|\[\]\/\\])/g, '\\$1'));
	const pattern = escapedWords && escapedWords.map((word) => `\[?${word}\]?`).join('[sS]*');
	const levelIndex = filters.level ? logLevels.indexOf(filters.level) : null;
	const validLevels = filters.level ? new Set(logLevels.filter((_, i) => i <= (levelIndex as number))) : null;
	const filterTypes = filters.types?.length ? new Set(filters.types) : null;

	return logs.filter((log) => {
		if (validLevels && !validLevels.has(log.level)) return false;
		if (pattern) {
			const regex = new RegExp(pattern, 'i');
			if (!regex.test(`[${log.level}]${log.message}`)) return false;
		}
		if (filterTypes) {
			const match = log.message.match(/^\[([^\]]+)\]/);
			const type = match ? match[1] : 'General';
			return filterTypes.has(type);
		}
		return true;
	});
};
