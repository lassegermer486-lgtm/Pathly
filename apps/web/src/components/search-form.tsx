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
  action = "/hochschulen",
  placeholder = "z. B. TU München, Hochschule Bremen …",
  label = "Hochschule suchen",
}: {
  defaultValue?: string;
  className?: string;
  children?: React.ReactNode;
  action?: string;
  placeholder?: string;
  label?: string;
}) {
  return (
    <form action={action} role="search" className={className}>
      <InputGroup className="h-11 bg-background">
        <InputGroupAddon>
          <SearchIcon />
        </InputGroupAddon>
        <InputGroupInput
          name="q"
          type="search"
          defaultValue={defaultValue}
          placeholder={placeholder}
          aria-label={label}
          className="text-base text-card-foreground"
        />
        <InputGroupAddon align="inline-end">
          <InputGroupButton type="submit" variant="default" size="sm" className="h-8 px-4 max-md:h-9">
            Suchen
          </InputGroupButton>
        </InputGroupAddon>
      </InputGroup>
      {children}
    </form>
  );
}
