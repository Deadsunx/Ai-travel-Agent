import { Bot } from 'lucide-react'
import { SkeletonLoader } from '@/components/ui/SkeletonLoader'

interface StreamingIndicatorProps {
    status: string
}

export default function StreamingIndicator({ status }: StreamingIndicatorProps) {
    return (
        <div className="flex gap-3 message-enter">
            {/* Avatar */}
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-primary-500 to-accent-500 
                      flex items-center justify-center text-white">
                <Bot className="w-4 h-4" />
            </div>

            {/* Status Message */}
            <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-3 min-w-[200px]">
                <div className="space-y-3">
                    {/* Thinking Skeletons */}
                    <div className="space-y-2">
                        <SkeletonLoader className="h-4 w-3/4 bg-gray-300/50" />
                        <SkeletonLoader className="h-4 w-1/2 bg-gray-300/50" />
                    </div>

                    {/* Status text */}
                    <div className="flex items-center gap-2 pt-1 border-t border-gray-200/50">
                        <div className="w-1.5 h-1.5 bg-primary-500 rounded-full animate-pulse"></div>
                        <span className="text-xs font-medium text-primary-600 uppercase tracking-wide">
                            {status || 'Processing...'}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    )
}
