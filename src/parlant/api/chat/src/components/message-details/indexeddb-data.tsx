import {getIndexedDBSize} from '@/lib/utils';
import {DB_NAME} from '@/utils/logs';
import {Trash} from 'lucide-react';
import {useEffect, useState} from 'react';
import {toast} from 'sonner';
import {twJoin} from 'tailwind-merge';

function clearIndexedDBData(dbName: string, objectStoreName: string) {
	return new Promise((resolve, reject) => {
		const request = indexedDB.open(dbName);

		request.onerror = (event) => {
			reject(event.target.error);
		};

		request.onsuccess = (event) => {
			const db = event.target.result;
			const transaction = db.transaction(objectStoreName, 'readwrite');
			const objectStore = transaction.objectStore(objectStoreName);
			const clearRequest = objectStore.clear();

			clearRequest.onsuccess = () => {
				resolve();
			};

			clearRequest.onerror = (clearEvent) => {
				reject(clearEvent.target.error);
			};

			transaction.oncomplete = () => {
				db.close();
			};
		};
	});
}

const IndexedDBData = () => {
	const [estimatedDataInMB, setEstimatedDataInMB] = useState<number | null>(null);

	const setData = async () => {
		const estimated = await getIndexedDBSize(DB_NAME);
		setEstimatedDataInMB(estimated);
	};

	async function handleClearDataClick() {
		try {
			await clearIndexedDBData('Parlant', 'logs');
			setData();
			toast.success('IndexedDB data cleared successfully.');
		} catch (e) {
			console.log('Error clearing IndexedDB data', e);
			toast.error('Error clearing IndexedDB data');
		}
	}

	useEffect(() => {
		setData();
	}, []);
	const dataInMB = estimatedDataInMB ? +estimatedDataInMB.toFixed(1) : null;
	return (
		<div className={twJoin('ps-[10px] text-[11px] flex items-center gap-[5px] z-[1] bg-white absolute bottom-0 w-full', !dataInMB && 'hidden')}>
			<div>The logs use approximately {dataInMB} MB of storage (indexedDB)</div>
			<Trash role='button' onClick={handleClearDataClick} size={13} />
		</div>
	);
};
export default IndexedDBData;
