import { AlertTriangle } from "lucide-react";

/**
 * Amounts and rates a model's reading states that its clause does not: the
 * reading needs checking before it is relied on.
 */
export default function UnsupportedNumbers({ numbers, className = "" }: { numbers?: string[] | null; className?: string }) {
  if (!numbers || numbers.length === 0) return null;
  return (
    <p className={`flex items-start gap-1.5 text-[12px] leading-snug text-status-warning ${className}`} role="note">
      <AlertTriangle className="mt-[1px] h-3.5 w-3.5 shrink-0" aria-hidden />
      <span>
        Needs review: {numbers.join(", ")} {numbers.length === 1 ? "is" : "are"} not in the clause
      </span>
    </p>
  );
}
