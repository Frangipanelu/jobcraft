import { describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import App from '../App';
import { createTestQueryClient } from './test-utils';

describe('App 入口', () => {
  it('未登录时渲染登录页', async () => {
    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <App />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText(/登录即表示同意/)).toBeInTheDocument());
  });
});