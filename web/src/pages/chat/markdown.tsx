import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Agent replies are Markdown. Raw HTML in them is not rendered (react-markdown's default). */
export function Markdown({ text }: { text: string }) {
  return (
    <div className="prose-chat text-[15px] md:text-sm">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{ a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" /> }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
