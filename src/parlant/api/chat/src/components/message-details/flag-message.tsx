import { EventInterface } from '@/utils/interfaces';
import { Textarea } from '../ui/textarea';
import { Button } from '../ui/button';
import { dialogAtom } from '@/store';
import { useAtom } from 'jotai';
import { addItemToIndexedDB, deleteItemFromIndexedDB } from '@/lib/utils';
import { useState } from 'react';
import MessageBubble from '../message/message-bubble';

interface FlagMessageProps {
	event: EventInterface;
	sessionId: string;
	onFlag?: (flagValue: string) => void;
	existingFlagValue?: string;
}   

const FlagMessage = ({event, sessionId, existingFlagValue, onFlag}: FlagMessageProps) => {
    const [dialog] = useAtom(dialogAtom);
    const [flagValue, setFlagValue] = useState(existingFlagValue || '');

    const flagMessage = async() => {
        await addItemToIndexedDB('Parlant-flags', 'message_flags', event.correlation_id, {sessionId, correlationId: event.correlation_id, flagValue: flagValue || 'This message is flagged'}, 'update', {name: 'sessionIndex', keyPath: 'sessionId'});
        onFlag?.(flagValue || '');
        dialog.closeDialog();
    };

    const unflagMessage = async() => {
        await deleteItemFromIndexedDB('Parlant-flags', 'message_flags', event.correlation_id);
        onFlag?.('');
        dialog.closeDialog();
    };

	return (
        <div className='p-3 flex flex-col gap-3 h-full'>
            <div className='message-bubble [&>*]:w-full [&_*]:cursor-default'>
                <MessageBubble event={event} isContinual={true} showLogs={() => {}} showLogsForMessage={null} />
            </div>
            <div>
                <p className='text-[14px] text-[#656565] w-[80%]'>
                Flagging a message is a handy feature that helps users keep track of important communications. When a message is flagged, it stands out in the inbox, making it easier to find later. This is especially useful for messages that require follow-up or contain critical information.
                </p>
            </div>
            <Textarea placeholder='Enter your flag reason' value={flagValue} onChange={(e) => setFlagValue(e.target.value)} className='!ring-0 !ring-offset-0 flex-1 !resize-none'/>
            <div className='flex justify-end gap-3'>
                <Button variant='outline' onClick={() => dialog.closeDialog()}>Cancel</Button>
                {existingFlagValue && <Button variant='outline' onClick={unflagMessage}>Unflag</Button>}
                <Button onClick={flagMessage}>Save</Button>
            </div>
        </div>
    )
};

export default FlagMessage;