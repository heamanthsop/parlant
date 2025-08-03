import Markdown from '../markdown/markdown';
import { twMerge } from 'tailwind-merge';
import Tooltip from '../ui/custom/tooltip';
import { copy } from '@/lib/utils';

const DraftBubble = ({draft = ''}) => {
	return (
		<div className='group/main flex'>
            <div className='text-gray-400 relative px-[22px] peer/draft py-[20px] bg-[#F5F6F8] rounded-[22px] mb-[16px] max-w-[min(560px,100%)]'>
                <Markdown className='leading-[26px]'>
                    {draft}
                </Markdown>
            </div>
            <div className={twMerge('mx-[10px] self-stretch relative invisible items-center flex group-hover/main:visible peer-hover:visible hover:visible')}>
                <Tooltip value='Copy' side='top'>
                    <div data-testid='copy-button' role='button' onClick={() => copy(draft|| '')} className='group cursor-pointer'>
                        <img src='icons/copy.svg' alt='edit' className='block opacity-50 rounded-[10px] group-hover:bg-[#EBECF0] size-[30px] p-[5px]' />
                    </div>
                </Tooltip>
            </div>
        </div>
	);
};

export default DraftBubble;