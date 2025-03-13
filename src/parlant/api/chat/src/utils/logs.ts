import {Log} from './interfaces';

const logLevels = ['WARNING', 'INFO', 'DEBUG'];
export const DB_NAME = 'Parlant';
const STORE_NAME = 'logs';

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
		count.onsuccess = () => console.log('ccc', count.result);
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
