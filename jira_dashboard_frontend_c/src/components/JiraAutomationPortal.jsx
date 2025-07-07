import React, { useState, useEffect } from 'react';
import { 
  Loader2, Bug, ClipboardList, BookOpen, Rocket, 
  PlusCircle, CheckCircle, XCircle, AlertCircle,
  ChevronRight, ChevronDown, Sparkles, TestTube,
  Link2, FileText, RefreshCw
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const JiraAutomationPortal = () => {
  // State management
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedIssue, setSelectedIssue] = useState(null);
  const [activeTab, setActiveTab] = useState('issues');
  
  // Automation state
  const [requirement, setRequirement] = useState('');
  const [automationLoading, setAutomationLoading] = useState(false);
  const [automationResult, setAutomationResult] = useState(null);
  const [expandedTasks, setExpandedTasks] = useState({});

  useEffect(() => {
    fetchIssues();
  }, []);

  const fetchIssues = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch('http://localhost:8000/api/issues/');
      if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
      const data = await response.json();
      setIssues(data.issues || []);
      setLoading(false);
    } catch (err) {
      setError(`Failed to fetch issues: ${err.message}`);
      setLoading(false);
    }
  };

  const fetchIssueDetails = async (issueKey) => {
    try {
      const response = await fetch(`http://localhost:8000/api/issues/${issueKey}/`);
      if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
      const data = await response.json();
      setSelectedIssue(data);
    } catch (err) {
      setError(`Failed to fetch issue details: ${err.message}`);
    }
  };

  const runAutomation = async () => {
    if (!requirement.trim()) {
      setError('Please enter a requirement');
      return;
    }

    try {
      setAutomationLoading(true);
      setError(null);
      setAutomationResult(null);

      const response = await fetch('http://localhost:8000/api/automation/workflow/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ requirement }),
      });

      if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
      
      const result = await response.json();
      setAutomationResult(result);
      
      // Refresh issues list to show new tickets
      setTimeout(fetchIssues, 2000);
      
    } catch (err) {
      setError(`Automation failed: ${err.message}`);
    } finally {
      setAutomationLoading(false);
    }
  };

  const toggleTaskExpansion = (taskKey) => {
    setExpandedTasks(prev => ({
      ...prev,
      [taskKey]: !prev[taskKey]
    }));
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'to do': return 'bg-gray-200 text-gray-700';
      case 'in progress': return 'bg-blue-100 text-blue-700';
      case 'done': return 'bg-green-100 text-green-700';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  const getIssuetypeIcon = (issuetype) => {
    switch (issuetype?.name?.toLowerCase()) {
      case 'bug': return <Bug size={20} />;
      case 'task': return <ClipboardList size={20} />;
      case 'story': return <BookOpen size={20} />;
      case 'epic': return <Rocket size={20} />;
      case 'subtask': return <TestTube size={20} />;
      default: return <ClipboardList size={20} />;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-cyan-50">
      {/* Header */}
      <header className="bg-white shadow-lg border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-3">
              <Sparkles className="text-indigo-600" />
              Jira Automation Portal
            </h1>
            <button
              onClick={fetchIssues}
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
              title="Refresh issues"
            >
              <RefreshCw size={20} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>
      </header>

      {/* Error Alert */}
      {error && (
        <div className="max-w-7xl mx-auto px-4 mt-4">
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2"
          >
            <AlertCircle size={20} />
            {error}
            <button 
              onClick={() => setError(null)}
              className="ml-auto text-red-500 hover:text-red-700"
            >
              <XCircle size={20} />
            </button>
          </motion.div>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="max-w-7xl mx-auto px-4 mt-8">
        <div className="flex gap-4 border-b border-gray-200">
          <button
            onClick={() => setActiveTab('issues')}
            className={`pb-4 px-6 font-medium transition-colors ${
              activeTab === 'issues'
                ? 'text-indigo-600 border-b-2 border-indigo-600'
                : 'text-gray-600 hover:text-gray-800'
            }`}
          >
            <div className="flex items-center gap-2">
              <ClipboardList size={20} />
              Issues
            </div>
          </button>
          <button
            onClick={() => setActiveTab('automation')}
            className={`pb-4 px-6 font-medium transition-colors ${
              activeTab === 'automation'
                ? 'text-indigo-600 border-b-2 border-indigo-600'
                : 'text-gray-600 hover:text-gray-800'
            }`}
          >
            <div className="flex items-center gap-2">
              <Sparkles size={20} />
              AI Automation
            </div>
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 py-8">
        <AnimatePresence mode="wait">
          {activeTab === 'issues' ? (
            <motion.div
              key="issues"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="grid grid-cols-1 lg:grid-cols-2 gap-8"
            >
              {/* Issues List */}
              <div className="bg-white rounded-xl shadow-lg p-6">
                <h2 className="text-xl font-semibold mb-4 text-gray-700">All Issues</h2>
                
                {loading ? (
                  <div className="flex justify-center items-center h-40">
                    <Loader2 className="animate-spin text-indigo-500" size={40} />
                  </div>
                ) : (
                  <div className="space-y-3 max-h-[600px] overflow-y-auto">
                    {issues.length > 0 ? (
                      issues.map(issue => (
                        <motion.div
                          key={issue.key}
                          whileHover={{ scale: 1.02 }}
                          className="cursor-pointer p-4 bg-gray-50 rounded-lg border border-gray-200 hover:border-indigo-300 transition-all"
                          onClick={() => fetchIssueDetails(issue.key)}
                        >
                          <div className="flex items-start gap-3">
                            <div className="text-indigo-500 mt-1">
                              {getIssuetypeIcon(issue.fields.issuetype)}
                            </div>
                            <div className="flex-1">
                              <h3 className="font-semibold text-gray-800">{issue.key}</h3>
                              <p className="text-gray-600 text-sm mt-1">{issue.fields.summary}</p>
                              <div className="flex flex-wrap gap-2 mt-2">
                                <span className={`px-2 py-1 rounded-full text-xs ${getStatusColor(issue.fields.status?.name)}`}>
                                  {issue.fields.status?.name || 'Unknown'}
                                </span>
                                <span className="text-xs text-gray-500">
                                  {issue.fields.assignee?.displayName || 'Unassigned'}
                                </span>
                              </div>
                            </div>
                          </div>
                        </motion.div>
                      ))
                    ) : (
                      <div className="text-center text-gray-400 py-8">No issues found</div>
                    )}
                  </div>
                )}
              </div>

              {/* Issue Details */}
              <div className="bg-white rounded-xl shadow-lg p-6">
                <h2 className="text-xl font-semibold mb-4 text-gray-700">Issue Details</h2>
                
                {selectedIssue ? (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="space-y-4"
                  >
                    <div>
                      <h3 className="text-lg font-bold text-gray-800">{selectedIssue.key}</h3>
                      <p className="text-gray-600 mt-1">{selectedIssue.fields?.summary}</p>
                    </div>

                    <div className="space-y-3">
                      <div className="flex items-center gap-2">
                        <span className={`px-3 py-1 rounded-full text-sm ${getStatusColor(selectedIssue.fields?.status?.name)}`}>
                          {selectedIssue.fields?.status?.name || 'Unknown'}
                        </span>
                        <span className="text-sm text-gray-500">
                          {selectedIssue.fields?.issuetype?.name}
                        </span>
                      </div>

                      <div className="bg-gray-50 p-4 rounded-lg space-y-2 text-sm">
                        <div><strong>Priority:</strong> {selectedIssue.fields?.priority?.name || 'Not set'}</div>
                        <div><strong>Assignee:</strong> {selectedIssue.fields?.assignee?.displayName || 'Unassigned'}</div>
                        <div><strong>Created:</strong> {new Date(selectedIssue.fields?.created).toLocaleDateString()}</div>
                      </div>

                      <div>
                        <h4 className="font-semibold mb-2">Description</h4>
                        <div className="bg-gray-50 p-4 rounded-lg text-sm">
                          {selectedIssue.fields?.description ? (
                            <div dangerouslySetInnerHTML={{ 
                              __html: typeof selectedIssue.fields.description === 'object' 
                                ? 'Complex formatting' 
                                : selectedIssue.fields.description 
                            }} />
                          ) : (
                            <em className="text-gray-400">No description</em>
                          )}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                ) : (
                  <div className="text-center text-gray-400 py-8">
                    Select an issue to view details
                  </div>
                )}
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="automation"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
            >
              {/* Automation Input */}
              <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
                <h2 className="text-xl font-semibold mb-4 text-gray-700 flex items-center gap-2">
                  <Sparkles className="text-indigo-500" />
                  AI-Powered Ticket Generation
                </h2>
                
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Enter your requirement
                    </label>
                    <textarea
                      value={requirement}
                      onChange={(e) => setRequirement(e.target.value)}
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors"
                      rows="4"
                      placeholder="E.g., Build a user authentication system with email verification and OAuth support..."
                    />
                  </div>
                  
                  <button
                    onClick={runAutomation}
                    disabled={automationLoading || !requirement.trim()}
                    className={`w-full py-3 px-6 rounded-lg font-medium transition-all flex items-center justify-center gap-2 ${
                      automationLoading || !requirement.trim()
                        ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                        : 'bg-indigo-600 text-white hover:bg-indigo-700 transform hover:scale-[1.02]'
                    }`}
                  >
                    {automationLoading ? (
                      <>
                        <Loader2 className="animate-spin" size={20} />
                        Generating tickets...
                      </>
                    ) : (
                      <>
                        <PlusCircle size={20} />
                        Generate Tickets & Test Cases
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Automation Results */}
              {automationResult && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="bg-white rounded-xl shadow-lg p-6"
                >
                  <h2 className="text-xl font-semibold mb-4 text-gray-700">Generation Results</h2>
                  
                  {/* Parent Ticket */}
                  <div className="mb-6">
                    <h3 className="font-semibold text-gray-700 mb-2 flex items-center gap-2">
                      <FileText className="text-blue-500" size={20} />
                      Parent Ticket
                    </h3>
                    <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                      <div className="flex items-center gap-2">
                        {automationResult.parent_ticket ? (
                          <>
                            <CheckCircle className="text-green-500" size={20} />
                            <span className="font-mono text-blue-700">{automationResult.parent_ticket}</span>
                            <span className="text-gray-600">- {automationResult.requirement}</span>
                          </>
                        ) : (
                          <>
                            <XCircle className="text-red-500" size={20} />
                            <span className="text-red-600">Failed to create parent ticket</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Development Tasks */}
                  <div className="mb-6">
                    <h3 className="font-semibold text-gray-700 mb-2 flex items-center gap-2">
                      <ClipboardList className="text-green-500" size={20} />
                      Development Tasks ({automationResult.development_tasks?.length || 0})
                    </h3>
                    <div className="space-y-3">
                      {automationResult.development_tasks?.map((task) => (
                        <div key={task.key} className="bg-gray-50 rounded-lg border border-gray-200">
                          <div 
                            className="p-4 cursor-pointer hover:bg-gray-100 transition-colors"
                            onClick={() => toggleTaskExpansion(task.key)}
                          >
                            <div className="flex items-start gap-3">
                              <div className="mt-1">
                                {expandedTasks[task.key] ? (
                                  <ChevronDown className="text-gray-500" size={20} />
                                ) : (
                                  <ChevronRight className="text-gray-500" size={20} />
                                )}
                              </div>
                              <div className="flex-1">
                                <div className="flex items-center gap-2">
                                  <CheckCircle className="text-green-500" size={16} />
                                  <span className="font-mono text-sm text-gray-700">{task.key}</span>
                                  <span className="px-2 py-1 bg-indigo-100 text-indigo-700 text-xs rounded-full">
                                    {task.category}
                                  </span>
                                </div>
                                <p className="font-medium text-gray-800 mt-1">{task.title}</p>
                                <p className="text-sm text-gray-600 mt-1">{task.summary}</p>
                              </div>
                            </div>
                          </div>
                          
                          {/* Test Cases */}
                          <AnimatePresence>
                            {expandedTasks[task.key] && automationResult.test_cases?.[task.key] && (
                              <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                className="border-t border-gray-200"
                              >
                                <div className="p-4 bg-orange-50">
                                  <h4 className="font-medium text-gray-700 mb-2 flex items-center gap-2">
                                    <TestTube className="text-orange-500" size={16} />
                                    Test Cases ({automationResult.test_cases[task.key]?.length || 0})
                                  </h4>
                                  <div className="space-y-2">
                                    {automationResult.test_cases[task.key]?.map((testCase) => (
                                      <div key={testCase.key} className="flex items-center gap-2 text-sm">
                                        <CheckCircle className="text-green-500" size={14} />
                                        <span className="font-mono text-gray-600">{testCase.key}</span>
                                        <span className="text-gray-700">{testCase.name}</span>
                                        <span className={`px-2 py-0.5 text-xs rounded-full ${
                                          testCase.priority === 'High' 
                                            ? 'bg-red-100 text-red-700'
                                            : testCase.priority === 'Medium'
                                            ? 'bg-yellow-100 text-yellow-700'
                                            : 'bg-green-100 text-green-700'
                                        }`}>
                                          {testCase.priority}
                                        </span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Errors */}
                  {automationResult.errors?.length > 0 && (
                    <div className="bg-red-50 p-4 rounded-lg border border-red-200">
                      <h3 className="font-semibold text-red-700 mb-2 flex items-center gap-2">
                        <AlertCircle size={20} />
                        Errors
                      </h3>
                      <ul className="list-disc list-inside space-y-1">
                        {automationResult.errors.map((error, idx) => (
                          <li key={idx} className="text-red-600 text-sm">{error}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </motion.div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default JiraAutomationPortal;