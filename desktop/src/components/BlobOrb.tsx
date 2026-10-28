import { memo } from "react";

export type OrbVisualState = "idle" | "listening" | "thinking" | "responding";

interface BlobOrbProps {
  state: OrbVisualState;
}

export const BlobOrb = memo(function BlobOrb({ state }: BlobOrbProps) {
  return (
    <div className={`orb orb--${state}`} aria-hidden="true">
      <span className="orb__aura" />
      <span className="orb__ring orb__ring--outer" />
      <span className="orb__ring orb__ring--middle" />
      <span className="orb__ring orb__ring--inner" />

      <span className="orb__shell">
        <span className="orb__shell-glow" />
        <span className="orb__shell-edge" />
        <span className="orb__refraction" />
        <span className="orb__inner-ring" />
      </span>

      <span className="orb__particles">
        <span className="orb__orbit orb__orbit--outer">
          <i />
          <i />
          <i />
          <i />
          <i />
          <i />
        </span>
        <span className="orb__orbit orb__orbit--middle">
          <i />
          <i />
          <i />
          <i />
          <i />
        </span>
        <span className="orb__orbit orb__orbit--inner">
          <i />
          <i />
          <i />
          <i />
        </span>
      </span>

      <span className={`orb__wave ${state === "responding" ? "orb__wave--active" : ""}`}>
        <span />
        <span />
        <span />
        <span />
        <span />
        <span />
        <span />
      </span>
    </div>
  );
});
