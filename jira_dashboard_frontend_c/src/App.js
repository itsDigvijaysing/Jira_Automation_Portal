import logo from './logo.svg';
import './App.css';
import JiraIssueTracker from './components/JiraIssueTracker.jsx';

function App() {
  return (
    <div className="App">
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
        <h1>Jira Issue Tracker WebPage</h1>
      </header>
      <main>
        <JiraIssueTracker />
      </main>
    </div>
  );
}

export default App;
