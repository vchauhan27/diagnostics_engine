import { AIMessage, ToolMessage } from "@langchain/langgraph-sdk";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronUp, CheckCircle2, Loader2 } from "lucide-react";

function isComplexValue(value: any): boolean {
  return Array.isArray(value) || (typeof value === "object" && value !== null);
}

/** Compact status pill for [Tool Update] system_update messages */
export function ToolUpdatePill({ content, isSpinning }: { content: string, isSpinning?: boolean }) {
  const label = content.replace(/^\[Tool Update\]\s*/i, "").replace(/\.\.\.$/, "");

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium w-fit bg-blue-50 border border-blue-100 text-blue-700 my-0.5"
    >
      {!isSpinning ? (
        <CheckCircle2 className="w-3.5 h-3.5 text-blue-500 flex-shrink-0" />
      ) : (
        <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin flex-shrink-0" />
      )}
      <span className="truncate max-w-xs">{label}</span>
    </motion.div>
  );
}

export function ToolCalls({
  toolCalls,
}: {
  toolCalls: AIMessage["tool_calls"];
}) {
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="space-y-4 w-full max-w-4xl">
      {toolCalls.map((tc, idx) => {
        const args = tc.args as Record<string, any>;
        const hasArgs = Object.keys(args).length > 0;
        return (
          <div key={idx} className="border border-gray-200 rounded-lg overflow-hidden">
            <div className="bg-gray-50 px-4 py-2 border-b border-gray-200">
              <h3 className="font-medium text-gray-900">
                {tc.name}
                {tc.id && (
                  <code className="ml-2 text-sm bg-gray-100 px-2 py-1 rounded">
                    {tc.id}
                  </code>
                )}
              </h3>
            </div>
            {hasArgs ? (
              <table className="min-w-full divide-y divide-gray-200">
                <tbody className="divide-y divide-gray-200">
                  {Object.entries(args).map(([key, value], argIdx) => (
                    <tr key={argIdx}>
                      <td className="px-4 py-2 text-sm font-medium text-gray-900 whitespace-nowrap">{key}</td>
                      <td className="px-4 py-2 text-sm text-gray-500">
                        {isComplexValue(value) ? (
                          <code className="bg-gray-50 rounded px-2 py-1 font-mono text-sm break-all">
                            {JSON.stringify(value, null, 2)}
                          </code>
                        ) : (
                          String(value)
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <code className="text-sm block p-3">{"{}"}</code>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function ToolResult({ message }: { message: ToolMessage }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const contentStr = String(message.content ?? "");
  const lc = contentStr.toLowerCase();

  // Simple success messages: render as a green badge
  const isSimpleSuccess =
    (lc.includes("successfully") || lc.includes("created") || lc.includes("ticket created")) &&
    contentStr.length < 120;

  if (isSimpleSuccess) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium w-fit bg-green-50 border border-green-200 text-green-700 my-0.5"
      >
        <CheckCircle2 className="w-3.5 h-3.5 text-green-500 flex-shrink-0" />
        <span>{contentStr}</span>
      </motion.div>
    );
  }

  const contentLines = contentStr.split("\n");
  const shouldTruncate = contentLines.length > 5 || contentStr.length > 600;
  const displayedContent =
    shouldTruncate && !isExpanded
      ? contentStr.length > 600
        ? contentStr.slice(0, 600) + "..."
        : contentLines.slice(0, 5).join("\n") + "\n..."
      : contentStr;

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden text-sm max-w-2xl">
      <div className="bg-gray-50 px-4 py-2 border-b border-gray-200 flex items-center justify-between gap-2">
        <h3 className="font-medium text-gray-900">Tool Result</h3>
        {message.tool_call_id && (
          <code className="text-xs bg-gray-100 px-2 py-0.5 rounded text-gray-500">
            {message.tool_call_id}
          </code>
        )}
      </div>
      <motion.div className="bg-gray-50" initial={false} animate={{ height: "auto" }} transition={{ duration: 0.3 }}>
        <div className="p-3">
          <AnimatePresence mode="wait" initial={false}>
            <motion.pre
              key={isExpanded ? "expanded" : "collapsed"}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18 }}
              className="text-xs font-mono text-gray-600 whitespace-pre-wrap break-all leading-relaxed"
            >
              {displayedContent}
            </motion.pre>
          </AnimatePresence>
        </div>
        {shouldTruncate && (
          <motion.button
            onClick={() => setIsExpanded(!isExpanded)}
            className="w-full py-2 flex items-center justify-center border-t border-gray-200 text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-all duration-200 cursor-pointer"
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.98 }}
          >
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </motion.button>
        )}
      </motion.div>
    </div>
  );
}
