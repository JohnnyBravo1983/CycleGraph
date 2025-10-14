// last inn jest-dom globalt (inkl. matchers)
import '@testing-library/jest-dom/vitest';

// valgfritt, men greit å beholde for sikkerhets skyld
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
});
