import { SearchIcon } from "lucide-react";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";

export function SearchForm({
  defaultValue,
  className,
  children,
}: {
  defaultValue?: string;
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <form action="/hochschulen" role="search" className={className}>
      <InputGroup className="h-11 bg-background">
        <InputGroupAddon>
          <SearchIcon />
        </InputGroupAddon>
        <InputGroupInput
          name="q"
          type="search"
          defaultValue={defaultValue}
          placeholder="z. B. TU München, Hochschule Bremen …"
          aria-label="Hochschule suchen"
          className="text-base text-card-foreground"
        />
        <InputGroupAddon align="inline-end">
          <InputGroupButton type="submit" variant="default" size="sm" className="h-8 px-4">
            Suchen
          </InputGroupButton>
        </InputGroupAddon>
      </InputGroup>
      {children}
    </form>
  );
}
