import { BaseCard } from "@/components/landing/BaseCard";

interface TestimonialCardProps {
  img: string;
  name: string;
  title: string;
  content: string;
}

export function TestimonialCard({ img, name, title, content }: TestimonialCardProps) {
  return (
    <BaseCard variant="testimonial" padding="lg" interactive className="h-full">
      <div className="mb-6 flex items-center gap-4">
        <div className="h-12 w-12 flex-shrink-0 overflow-hidden rounded-full">
          <img className="h-full w-full object-cover" src={img} alt={name} />
        </div>
        <div className="min-w-0">
          <h4 className="truncate text-sm font-bold text-on-surface">{name}</h4>
          <p className="truncate text-xs text-on-surface-variant">{title}</p>
        </div>
      </div>
      <p className="leading-relaxed text-on-surface-variant">"{content}"</p>
    </BaseCard>
  );
}
