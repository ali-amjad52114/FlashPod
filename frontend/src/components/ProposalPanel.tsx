export function ProposalPanel(props: { proposal: string | null }) {
  return (
    <pre
      className="mono"
      style={{
        margin: 0,
        padding: 16,
        background: "var(--sheet)",
        border: "1px solid var(--hairline)",
        borderRadius: "var(--radius)",
        fontSize: 12,
        lineHeight: 1.5,
        whiteSpace: "pre-wrap",
        overflowX: "auto",
        maxHeight: 520,
      }}
    >
      {props.proposal || "No proposal text returned."}
    </pre>
  );
}
