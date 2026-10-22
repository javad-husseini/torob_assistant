import { useId, useMemo, useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandInput,
  CommandList,
  CommandGroup,
  CommandItem,
  CommandEmpty,
} from "@/components/ui/command";
import { normalizeFa } from "@/lib/api";

export function SearchCombobox({
  value,
  options,
  onChange,
  label,
  id,
}: {
  value: string;
  options: string[];
  onChange: (value: string) => void;
  label: string;
  id?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const listId = useId();
  const matches = useMemo(
    () =>
      options
        .filter((option) => normalizeFa(option).includes(normalizeFa(query)))
        .slice(0, 80),
    [options, query],
  );
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          variant="outline"
          className="w-full justify-between"
          aria-label={label}
        >
          <span className="truncate">{value || label}</span>
          <ChevronsUpDown data-icon="inline-end" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 p-0" dir="rtl">
        <Command shouldFilter={false}>
          <CommandInput
            placeholder={`جست‌وجوی ${label}…`}
            value={query}
            onValueChange={setQuery}
          />
          <CommandList id={listId}>
            <CommandEmpty>گزینه‌ای در داده‌ها پیدا نشد.</CommandEmpty>
            <CommandGroup>
              <CommandItem
                value="all"
                onSelect={() => {
                  onChange("");
                  setOpen(false);
                }}
              >
                همهٔ گزینه‌ها
              </CommandItem>
              {matches.map((option) => (
                <CommandItem
                  key={option}
                  value={option}
                  onSelect={() => {
                    onChange(option);
                    setOpen(false);
                  }}
                >
                  <span className="min-w-0 flex-1">{option}</span>
                  {value === option && <Check />}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
