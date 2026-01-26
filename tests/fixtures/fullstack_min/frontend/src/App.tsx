/**
 * Minimal React App component for testing.
 */

interface AppProps {
  title?: string;
}

export function App({ title = "Hello" }: AppProps) {
  return (
    <div className="app">
      <h1>{title}</h1>
      <p>Welcome to the app</p>
    </div>
  );
}

export default App;
