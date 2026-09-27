import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, XCircle, ChevronDown, ChevronUp, AlertTriangle } from "lucide-react";
import { useStreamContext } from "@/providers/Stream";

interface JiraApprovalPayload {
  action: "approve_jira_ticket";
  message: string;
  diagnosis: {
    root_cause: string;
    probable_cause: string;
    severity: string;
    priority: string;
    suggested_fix: string;
    affected_component: string;
  };
}

function isJiraApprovalPayload(v: any): v is JiraApprovalPayload {
  return v && v.action === "approve_jira_ticket";
}

/** Card shown when the graph interrupts for Jira ticket approval */
function JiraApprovalCard({ interrupt }: { interrupt: JiraApprovalPayload }) {
  const [notes, setNotes] = useState("");
  const [detailsOpen, setDetailsOpen] = useState(false);
  const stream = useStreamContext();
  const d = interrupt.diagnosis;

  const respond = (approved: boolean) => {
    stream.submit(undefined, {
      command: { resume: { approved, notes: notes.trim() } },
      streamMode: ["values"],
    });
  };

  const priorityColor = d.priority?.toLowerCase().includes("p1") || d.severity?.toLowerCase() === "high"
    ? "text-red-600 bg-red-50 border-red-200"
    : d.priority?.toLowerCase().includes("p2")
    ? "text-orange-600 bg-orange-50 border-orange-200"
    : "text-blue-600 bg-blue-50 border-blue-200";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="w-full max-w-2xl border border-amber-200 rounded-xl overflow-hidden shadow-sm bg-white"
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-3.5 bg-amber-50 border-b border-amber-200">
        <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0" />
        <span className="text-sm font-semibold text-amber-800">Jira Ticket — Awaiting Approval</span>
        <span className={`ml-auto text-xs font-medium px-2.5 py-0.5 rounded-full border ${priorityColor}`}>
          {d.priority || d.severity || "Unknown priority"}
        </span>
      </div>

      {/* Diagnosis summary */}
      <div className="px-5 py-4 space-y-3">
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-0.5">Root Cause</p>
          <p className="text-sm text-gray-800">{d.root_cause}</p>
        </div>
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-0.5">Affected Component</p>
          <p className="text-sm text-gray-700">{d.affected_component}</p>
        </div>

        {/* Collapsible details */}
        <button
          onClick={() => setDetailsOpen((o) => !o)}
          className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 transition-colors cursor-pointer mt-1"
        >
          {detailsOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          {detailsOpen ? "Hide details" : "Show full diagnosis"}
        </button>
        <AnimatePresence>
          {detailsOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
              className="space-y-3 overflow-hidden"
            >
              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-0.5">Probable Cause</p>
                <p className="text-sm text-gray-700">{d.probable_cause}</p>
              </div>
              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-0.5">Suggested Fix</p>
                <p className="text-sm text-gray-700">{d.suggested_fix}</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Notes textarea */}
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Optional: add notes or rejection reason..."
          rows={2}
          className="w-full mt-2 text-sm border border-gray-200 rounded-lg px-3 py-2 resize-none
                     focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-transparent
                     placeholder:text-gray-400 bg-gray-50"
        />
      </div>

      {/* Action buttons */}
      <div className="flex gap-2 px-5 pb-4">
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.97 }}
          onClick={() => respond(true)}
          className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg
                     bg-green-600 hover:bg-green-700 text-white text-sm font-semibold
                     transition-colors shadow-sm cursor-pointer"
        >
          <CheckCircle2 className="w-4 h-4" />
          Approve & Create Ticket
        </motion.button>
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.97 }}
          onClick={() => respond(false)}
          className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg
                     bg-white hover:bg-red-50 text-red-600 border border-red-200 text-sm font-semibold
                     transition-colors shadow-sm cursor-pointer"
        >
          <XCircle className="w-4 h-4" />
          Reject
        </motion.button>
      </div>
    </motion.div>
  );
}

/** Generic fallback for non-Jira interrupts */
function GenericFallbackView({ interrupt }: { interrupt: Record<string, any> | Record<string, any>[] }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const contentStr = JSON.stringify(interrupt, null, 2);
  const lines = contentStr.split("\n");
  const shouldTruncate = lines.length > 4 || contentStr.length > 500;
  const displayed = shouldTruncate && !isExpanded
    ? contentStr.slice(0, 500) + "..."
    : contentStr;

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden max-w-2xl">
      <div className="bg-gray-50 px-4 py-2 border-b border-gray-200">
        <h3 className="font-medium text-gray-900 text-sm">Human Interrupt</h3>
      </div>
      <div className="p-3 bg-gray-50">
        <pre className="text-xs font-mono text-gray-600 whitespace-pre-wrap break-all">{displayed}</pre>
        {shouldTruncate && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="mt-2 flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 cursor-pointer"
          >
            {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {isExpanded ? "Show less" : "Show more"}
          </button>
        )}
      </div>
    </div>
  );
}

export function GenericInterruptView({
  interrupt,
}: {
  interrupt: Record<string, any> | Record<string, any>[];
}) {
  if (!Array.isArray(interrupt) && isJiraApprovalPayload(interrupt)) {
    return <JiraApprovalCard interrupt={interrupt} />;
  }
  return <GenericFallbackView interrupt={interrupt} />;
}
