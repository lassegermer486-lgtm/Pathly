import Link from "next/link";
import { CompassIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";

export default function NotFound() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 items-center px-4 py-24 sm:px-6">
      <Empty>
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <CompassIcon />
          </EmptyMedia>
          <EmptyTitle>Diesen Weg gibt es nicht</EmptyTitle>
          <EmptyDescription>
            Die Seite wurde verschoben oder existiert nicht.
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button nativeButton={false} render={<Link href="/hochschulen" />}>
            Zu den Hochschulen
          </Button>
        </EmptyContent>
      </Empty>
    </main>
  );
}
