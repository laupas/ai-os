import { useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Sparkles } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ListView } from "@/components/list-view";
import { ErrorBox, Loading, Page, PageHeader } from "@/components/page";
import { HistoryButton } from "@/components/history-button";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Hint, Input, Label, Textarea } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { api, type Skill } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { href } from "@/lib/router";
import { useAgents } from "./agents-page";

export function SkillsPage() {
  const { data, isLoading, error } = useAgents();
  const [editing, setEditing] = useState<Skill | "new" | null>(null);
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} />;
  return (
    <Page className="max-w-3xl">
      <PageHeader
        title="Skills"
        description="Instructions an agent loads when a task calls for them. Which agent may use a skill is set on the agent."
        actions={
          <Button onClick={() => setEditing("new")}>
            <Plus /> New skill
          </Button>
        }
      />
      <ListView
        items={data.skills}
        keyOf={(s) => s.name}
        text={(s) => `${s.name} ${s.description}`}
        facets={[{ label: "agents", value: (s) => (s.agents.length ? s.agents : "unused") }]}
        empty="No skills yet."
      >
        {(s) => <SkillCard skill={s} onEdit={() => setEditing(s)} />}
      </ListView>
      <Sheet open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <SheetContent side="right" className="gap-0 p-0 sm:max-w-2xl">
          {editing !== null ? <SkillForm skill={editing === "new" ? null : editing} onDone={() => setEditing(null)} /> : null}
        </SheetContent>
      </Sheet>
    </Page>
  );
}

function SkillCard({ skill, onEdit }: { skill: Skill; onEdit: () => void }) {
  return (
    <Card className="p-4">
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
          <Sparkles className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{skill.name}</span>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{skill.description}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Used by{" "}
            {skill.agents.length
              ? skill.agents.map((a, i) => (
                  <span key={a}>
                    {i ? ", " : ""}
                    <a className="underline" href={href("agents", a)}>
                      {a}
                    </a>
                  </span>
                ))
              : "no agent yet: grant it on an agent's page"}
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={onEdit}>
          <Pencil /> Edit
        </Button>
      </div>
    </Card>
  );
}

function SkillForm({ skill: s, onDone }: { skill: Skill | null; onDone: () => void }) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [name, setName] = useState("");
  const [description, setDescription] = useState(s?.description ?? "");
  const [content, setContent] = useState(s?.content ?? "");
  const [busy, setBusy] = useState(false);
  const done = () => {
    void queryClient.invalidateQueries({ queryKey: ["agents"] });
    onDone();
  };
  const save = async () => {
    setBusy(true);
    try {
      const body = { description: description.trim(), content };
      if (s) await api("PUT", `/api/skills/${encodeURIComponent(s.name)}`, body);
      else await api("POST", "/api/skills", { ...body, name: name.trim() });
      toast.success(s ? "Saved. Applies to the next turn." : "Created. Now grant it on an agent's page.");
      done();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    if (!s) return;
    const ok = await confirm({ title: `Delete ${s.name}?`, body: "Agents that have it lose it.", action: "Delete", destructive: true });
    if (!ok) return;
    try {
      await api("DELETE", `/api/skills/${encodeURIComponent(s.name)}`);
      done();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <form
      className="flex h-full flex-col"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <SheetHeader className="border-b">
        <SheetTitle>{s ? s.name : "New skill"}</SheetTitle>
        <SheetDescription>
          Applies to the next turn.
        </SheetDescription>
      </SheetHeader>
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
        {s ? null : (
          <Label>
            Name
            <Input required pattern="[a-z][a-z0-9\-]*" value={name} onChange={(e) => setName(e.target.value)} placeholder="travel-style" />
            <Hint>Lower-case letters, digits and dashes.</Hint>
          </Label>
        )}
        <Label>
          When to use it
          <Textarea required rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
          <Hint>The agent reads this to decide whether to load the skill, so say when it applies.</Hint>
        </Label>
        <Label className="flex-1">
          Instructions
          <Textarea
            required
            spellCheck={false}
            className="min-h-80 flex-1 font-mono text-xs md:text-xs"
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
          <Hint>Markdown, loaded as written.</Hint>
        </Label>
      </div>
      <div className="flex gap-2 border-t p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]">
        <Button type="submit" disabled={busy} className="flex-1 sm:flex-none">
          {s ? "Save" : "Create"}
        </Button>
        <Button type="button" variant="outline" onClick={onDone}>
          Cancel
        </Button>
        {s ? <HistoryButton kind="skills" id={s.name} onRestored={onDone} /> : null}
        <span className="flex-1" />
        {s ? (
          <Button type="button" variant="ghost" className="text-destructive" onClick={remove}>
            Delete
          </Button>
        ) : null}
      </div>
    </form>
  );
}
