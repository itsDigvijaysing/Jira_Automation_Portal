import { render, screen } from '@testing-library/react';
import App from './App';

beforeEach(() => {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve({ issues: [] }) })
  );
});

test('renders the portal and loads issues', async () => {
  render(<App />);
  expect(screen.getByText(/jira automation portal/i)).toBeInTheDocument();
  expect(await screen.findByText(/no issues found/i)).toBeInTheDocument();
  expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/issues/'));
});
