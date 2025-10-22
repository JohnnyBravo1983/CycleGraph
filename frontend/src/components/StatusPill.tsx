// src/components/StatusPill.tsx
import React from 'react';
export type PublishState = "pending" | "done" | "failed" | "skipped";

type Props = {
  state?: PublishState;
};

const labelMap: Record<PublishState, string> = {
  pending: 'Pending',
  done: 'Published',
  failed: 'Failed',
  skipped: 'Skipped',
};

export const StatusPill: React.FC<Props> = ({ state = 'pending' }) => {
  const label = labelMap[state] ?? state;

  const styles: Record<PublishState, string> = {
    pending: 'bg-yellow-100 text-yellow-800 ring-yellow-200',
    done: 'bg-green-100 text-green-800 ring-green-200',
    failed: 'bg-red-100 text-red-800 ring-red-200',
    skipped: 'bg-gray-100 text-gray-800 ring-gray-200',
  };

  const icon: Record<PublishState, string> = {
    pending: '⏳',
    done: '✓',
    failed: '⚠️',
    skipped: '⏭️',
  };

  return (
    <span
      data-testid="publish-pill"
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-sm ring-1 ${styles[state]}`}
    >
      <span aria-hidden>{icon[state]}</span>
      {label}
    </span>
  );
};
