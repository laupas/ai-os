import { CopyPlus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Hint, Input, Label } from "@/components/ui/input";

const NAME = /^[a-z][a-z0-9_-]{0,40}$/;

/** Makes a copy of an agent or a skill under a new name, through the same create
 * call as a new one, so every check of a save applies. */
export function DuplicateButton({
  what,
  original,
  create,
  onDone,
}: {
  what: string;
  original: string;
  create: (name: string) => Promise<unknown>;
  onDone?: (name: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    const chosen = name.trim();
    if (!NAME.test(chosen)) return toast.error("A name is lower-case letters, digits, - and _.");
    setBusy(true);
    try {
      await create(chosen);
      toast.success(`${chosen} is a copy of ${original}.`);
      setOpen(false);
      onDone?.(chosen);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={() => {
          setName(`${original}-copy`);
          setOpen(true);
        }}
      >
        <CopyPlus /> Duplicate
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md">
          <form
            className="grid gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              void submit();
            }}
          >
            <div className="space-y-1">
              <DialogTitle>Duplicate {original}</DialogTitle>
              <DialogDescription>
                A new {what} with everything {original} has, under a name of its own. It is not linked to {original} afterwards, nor to the Store.
              </DialogDescription>
            </div>
            <Label>
              Name
              <Input value={name} onChange={(e) => setName(e.target.value)} autoFocus spellCheck={false} />
              <Hint>Lower-case letters, digits, - and _.</Hint>
            </Label>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={busy}>
                <CopyPlus /> {busy ? "Copying…" : "Duplicate"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
