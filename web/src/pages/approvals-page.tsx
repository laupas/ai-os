import { useQuery } from "@tanstack/react-query";
import { Empty, ErrorBox, Loading, Page, PageHeader } from "@/components/page";
import { api, type Approval } from "@/lib/api";
import { href } from "@/lib/router";
import { when } from "@/lib/utils";
import { AskCard } from "./chat/message-views";

export function ApprovalsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["approvals"],
    queryFn: () => api<{ approvals: Approval[] }>("GET", "/api/approvals"),
    refetchInterval: 10_000,
  });
  return (
    <Page className="max-w-3xl">
      <PageHeader title="Approvals" description="Questions ai-os is waiting on, from every channel. The first answer wins." />
      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}
      {data?.approvals.length === 0 ? <Empty>Nothing is waiting for an answer.</Empty> : null}
      {data?.approvals.map((a) => (
        <AskCard
          key={a.id}
          id={a.id}
          question={a.question}
          options={a.options}
          context={
            <span className="font-normal">
              · {a.channel} · {when(a.created_at)} ·{" "}
              <a className="underline" href={href("chat", a.conversation_id)}>
                conversation
              </a>
            </span>
          }
        />
      ))}
    </Page>
  );
}
