import {clsx, type ClassValue} from 'clsx';
import {toast} from 'sonner';
import {twMerge} from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}

export const isSameDay = (dateA: string | Date, dateB: string | Date): boolean => {
	if (!dateA) return false;
	return new Date(dateA).toLocaleDateString() === new Date(dateB).toLocaleDateString();
};

export const copy = (text: string, element?: HTMLElement) => {
	if (navigator.clipboard && navigator.clipboard.writeText) {
		navigator.clipboard
			.writeText(text)
			.then(() => toast.info(text?.length < 100 ? `Copied text: ${text}` : 'Text copied'))
			.catch(() => {
				fallbackCopyText(text, element);
			});
	} else {
		fallbackCopyText(text, element);
	}
};

export const fallbackCopyText = (text: string, element?: HTMLElement) => {
	const textarea = document.createElement('textarea');
	textarea.value = text;
	(element || document.body).appendChild(textarea);
	textarea.style.position = 'fixed';
	textarea.select();
	try {
		const successful = document.execCommand('copy');
		if (successful) {
			toast.info(text?.length < 100 ? `Copied text: ${text}` : 'Text copied');
		} else {
			console.error('Fallback: Copy command failed.');
		}
	} catch (error) {
		console.error('Fallback: Unable to copy', error);
	} finally {
		(element || document.body).removeChild(textarea);
	}
};

export async function getIndexedDBSize(dbName: string): Promise<number> {
	// const estimation = await navigator.storage.estimate();
	// if (estimation?.usageDetails?.indexedDB) {
	// 	const valueInBytes = estimation.usageDetails.indexedDB;
	// 	const valueInMB = +(valueInBytes / (1024 * 1024)).toFixed(2);
	// 	return Promise.resolve(valueInMB);
	// }
	return new Promise((resolve, reject) => {
		const request = indexedDB.open(dbName);

		request.onerror = (event) => {
			reject(event.target.error);
		};

		request.onsuccess = (event) => {
			const db = event.target.result;
			let totalSize = 0;

			const objectStoreNames = Array.from(db.objectStoreNames);

			const transaction = db.transaction(objectStoreNames, 'readonly');

			let completedObjectStores = 0;

			objectStoreNames.forEach((storeName) => {
				const objectStore = transaction.objectStore(storeName);
				const cursorRequest = objectStore.openCursor();

				cursorRequest.onsuccess = (cursorEvent) => {
					const cursor = cursorEvent.target.result;
					if (cursor) {
						totalSize += estimateSize(cursor.key);
						totalSize += estimateSize(cursor.value);
						cursor.continue();
					} else {
						completedObjectStores++;
						if (completedObjectStores === objectStoreNames.length) {
							resolve(totalSize / (1024 * 1024)); // Convert to MB
						}
					}
				};

				cursorRequest.onerror = (cursorErrorEvent) => {
					reject(cursorErrorEvent.target.error);
				};
			});

			transaction.oncomplete = () => {
				db.close();
			};
		};
	});
}

function estimateSize(value) {
	if (typeof value === 'string') {
		return value.length * 2; // UTF-16: 2 bytes per character
	} else if (typeof value === 'number') {
		return 8; // Assuming 8 bytes for a double
	} else if (typeof value === 'boolean') {
		return 4;
	} else if (typeof value === 'object' && value !== null) {
		if (Array.isArray(value)) {
			let size = 0;
			value.forEach((item) => {
				size += estimateSize(item);
			});
			return size;
		} else {
			let size = 0;
			for (const key in value) {
				if (value.hasOwnProperty(key)) {
					size += estimateSize(key);
					size += estimateSize(value[key]);
				}
			}
			return size;
		}
	} else {
		return 0; // Other types (null, undefined, etc.)
	}
}

// Example usage:
async function example() {
	try {
		const sizeMB = await getIndexedDBSize('myDatabase');
		console.log(`IndexedDB size: ${sizeMB.toFixed(2)} MB`);
	} catch (error) {
		console.error('Error:', error);
	}
}

example();

export const timeAgo = (date: Date): string => {
	date = new Date(date);
	const now = new Date();
	const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
	const minutes = Math.floor(seconds / 60);
	const hours = Math.floor(minutes / 60);
	const days = Math.floor(hours / 24);
	// const weeks = Math.floor(days / 7);
	// const months = Math.floor(days / 30);
	const years = Math.floor(days / 365);

	if (seconds < 60) return 'less than a minute ago';
	if (minutes < 60) return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
	if (hours < 24) return date.toLocaleTimeString('en-US', {hour: 'numeric', minute: 'numeric', hour12: false});
	else return date.toLocaleString('en-US', {year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric', hour12: false});
	// if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`;
	// if (days === 1) return 'yesterday';
	// if (days < 7) return `${days} days ago`;
	// if (weeks === 1) return 'last week';
	// if (weeks < 4) return `${weeks} weeks ago`;
	// if (months === 1) return 'a month ago';
	// if (months < 12) return `${months} months ago`;
	// if (years === 1) return 'last year';
	return `${years} years ago`;
};

getIndexedDBSize('Parlant').then((a) => console.log('sizee', a));
