import { describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import App from '../App';

describe('App 入口', () => {
  it('未登录时渲染登录页', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText(/登录即表示同意/)).toBeInTheDocument());
  });
});