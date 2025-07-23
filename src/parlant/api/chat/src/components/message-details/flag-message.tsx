import { EventInterface } from '@/utils/interfaces';
import { Textarea } from '../ui/textarea';
import { Button } from '../ui/button';
import { dialogAtom } from '@/store';
import { useAtom } from 'jotai';
import { addItemToIndexedDB } from '@/lib/utils';
import { useState } from 'react';

interface FlagMessageProps {
	event: EventInterface;
	sessionId: string;
}   

const FlagMessage = ({event, sessionId}: FlagMessageProps) => {
    const [dialog] = useAtom(dialogAtom);
    const [flagValue, setFlagValue] = useState('');
	return (
        <div className='p-3 flex flex-col gap-3 h-full'>
            <p className='italic'>"{event.data?.message}"</p>
            <Textarea placeholder='Enter your flag reason' value={flagValue} onChange={(e) => setFlagValue(e.target.value)} className='!ring-0 !ring-offset-0 flex-1 !resize-none'/>
            <div className='flex justify-end gap-3'>
                <Button variant='outline' onClick={() => dialog.closeDialog()}>Cancel</Button>
                <Button onClick={() => addItemToIndexedDB('message_flags', event.correlation_id, {sessionId, flagValue}, 'update', {name: 'sessionIndex', keyPath: 'sessionId'})}>Flag</Button>
            </div>
        </div>
    )
};

export default FlagMessage;