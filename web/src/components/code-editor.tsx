import { json } from "@codemirror/lang-json";
import { markdown } from "@codemirror/lang-markdown";
import { python } from "@codemirror/lang-python";
import { yaml } from "@codemirror/lang-yaml";
import { EditorState, type Extension } from "@codemirror/state";
import { oneDark } from "@codemirror/theme-one-dark";
import { EditorView, basicSetup } from "codemirror";
import { useEffect, useRef } from "react";

function language(path: string): Extension[] {
  if (/\.ya?ml$/.test(path)) return [yaml()];
  if (/\.md$/.test(path)) return [markdown()];
  if (/\.py$/.test(path)) return [python()];
  if (/\.json$/.test(path)) return [json()];
  return [];
}

/** CodeMirror for one file: highlighted by its extension, dark when the page is.
 * Loaded on demand (it is most of a megabyte), see `repository-panel.tsx`. */
export default function CodeEditor({
  path,
  value,
  onChange,
  readOnly = false,
}: {
  path: string;
  value: string;
  onChange?: (value: string) => void;
  readOnly?: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const changed = useRef(onChange);
  changed.current = onChange;

  // A new editor for a new file or mode; the text is pushed in below without one.
  useEffect(() => {
    const dark = document.documentElement.classList.contains("dark");
    view.current = new EditorView({
      parent: host.current!,
      state: EditorState.create({
        doc: value,
        extensions: [
          basicSetup,
          ...language(path),
          ...(dark ? [oneDark] : []),
          EditorState.readOnly.of(readOnly),
          EditorView.editable.of(!readOnly),
          EditorView.lineWrapping,
          EditorView.updateListener.of((u) => u.docChanged && changed.current?.(u.state.doc.toString())),
          EditorView.theme({ "&": { fontSize: "12px", height: "100%" }, ".cm-scroller": { fontFamily: "var(--font-mono, ui-monospace, monospace)" } }),
        ],
      }),
    });
    return () => view.current?.destroy();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, readOnly]);

  useEffect(() => {
    const v = view.current;
    if (v && v.state.doc.toString() !== value) v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: value } });
  }, [value]);

  return <div ref={host} className="h-full min-h-64 overflow-hidden rounded-md border" />;
}
