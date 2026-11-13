import React, { useState, useEffect, useCallback } from 'react';
import {
  Loader2, Bug, ClipboardList, BookOpen, Rocket,
  PlusCircle, CheckCircle, XCircle, AlertCircle,
  ChevronRight, ChevronDown, Sparkles, TestTube,
  FileText, RefreshCw
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// API base URL — override with REACT_APP_API_BASE_URL (see .env.example).
const API_BASE = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

// Safely format a date string; Jira fields can be missing/invalid.
const formatDate = (value) => {
  if (!value) return '—';
  const d = new Date(value);
  return isNaN(d.getTime()) ? '—' : d.toLocaleDateString();
};

// Jira's v3 API returns descriptions as Atlassian Document Format (a JSON tree).
// Flatten it to plain text: each block on its own line, hard breaks as newlines.
const INLINE_ADF_TYPES = ['text', 'hardBreak', 'mention', 'emoji', 'inlineCard'];

const adfToText = (node) => {
  if (!node) return '';
  if (typeof node === 'string') return node;
  if (node.type === 'text') return node.text || '';
  if (node.type === 'hardBreak') return '\n';
  if (node.type === 'mention' || node.type === 'emoji') return node.attrs?.text || '';
  if (node.type === 'inlineCard') return node.attrs?.url || '';
  const children = Array.isArray(node.content) ? node.content : [];
  return children
    .map((child) => adfToText(child) + (INLINE_ADF_TYPES.includes(child?.type) ? '' : '\n'))
    .join('')
    .replace(/\n{3,}/g, '\n\n');
};

// Build an Error from a failed response, preferring the backend's {"error": ...} message.
const responseError = async (response) => {
  let detail = '';
  try {
    detail = (await response.json())?.error || '';
  } catch (parseError) {
    // Not JSON (e.g. an HTML error page): fall back to the status code.
  }
  return new Error(detail || `HTTP error! Status: ${response.status}`);
};

const getPriorityColor = (priority) => {
  switch (priority?.toLowerCase()) {
    case 'highest':
    case 'high':
      return 'bg-red-100 text-red-700';
    case 'medium':
      return 'bg-yellow-100 text-yellow-700';
    case 'low':
    case 'lowest':
      return 'bg-green-100 text-green-700';
    default:
      return 'bg-jira-gray-100 text-jira-gray-700';
  }
};

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

  const fetchIssues = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${API_BASE}/api/issues/`);
      if (!response.ok) throw await responseError(response);
      const data = await response.json();
      setIssues(data.issues || []);
    } catch (err) {
      setError(`Failed to fetch issues: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchIssues();
  }, [fetchIssues]);

  const fetchIssueDetails = async (issueKey) => {
    try {
      setError(null);
      const response = await fetch(`${API_BASE}/api/issues/${encodeURIComponent(issueKey)}/`);
      if (!response.ok) throw await responseError(response);
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

      const response = await fetch(`${API_BASE}/api/automation/workflow/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ requirement }),
      });

      if (!response.ok) throw await responseError(response);

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
      case 'to do': 
      case 'open':
      case 'backlog':
        return 'bg-jira-gray-100 text-jira-gray-800';
      case 'in progress': 
      case 'in review':
      case 'reviewing':
        return 'bg-blue-100 text-blue-800 border border-blue-200';
      case 'done': 
      case 'closed':
      case 'resolved':
        return 'bg-green-100 text-green-800 border border-green-200';
      case 'blocked':
      case 'on hold':
        return 'bg-red-100 text-red-800 border border-red-200';
      case 'testing':
      case 'qa':
        return 'bg-yellow-100 text-yellow-800 border border-yellow-200';
      default: 
        return 'bg-jira-gray-100 text-jira-gray-700';
    }
  };

  const getIssuetypeIcon = (issuetype) => {
    switch (issuetype?.name?.toLowerCase()) {
      case 'bug': return <Bug size={20} />;
      case 'task': return <ClipboardList size={20} />;
      case 'story': return <BookOpen size={20} />;
      case 'epic': return <Rocket size={20} />;
      case 'subtask':
      case 'sub-task': return <TestTube size={20} />;
      default: return <ClipboardList size={20} />;
    }
  };

  return (
    <div className="min-h-screen bg-jira-gray-50">
      {/* Header */}
      <header className="bg-white shadow-jira border-b border-jira-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-8 h-8 bg-jira-blue rounded flex items-center justify-center">
                <Sparkles className="text-white" size={20} />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-jira-gray-900">
                  Jira Automation Portal
                </h1>
                <p className="text-sm text-jira-gray-600">AI-powered ticket generation and management</p>
              </div>
            </div>
            <button
              onClick={fetchIssues}
              className="jira-button-secondary flex items-center gap-2"
              title="Refresh issues"
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      {/* Error Alert */}
      {error && (
        <div className="max-w-7xl mx-auto px-6 mt-4">
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-red-50 border-l-4 border-jira-red text-red-800 px-4 py-3 rounded-r-lg flex items-center gap-3"
          >
            <AlertCircle size={20} className="text-jira-red flex-shrink-0" />
            <span className="flex-1">{error}</span>
            <button 
              onClick={() => setError(null)}
              className="text-red-500 hover:text-red-700 transition-colors"
            >
              <XCircle size={18} />
            </button>
          </motion.div>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="max-w-7xl mx-auto px-6 mt-6">
        <div className="border-b border-jira-gray-200 bg-white rounded-t-lg">
          <div className="flex">
            <button
              onClick={() => setActiveTab('issues')}
              className={`flex items-center gap-2 px-6 py-4 font-medium transition-all border-b-2 ${
                activeTab === 'issues'
                  ? 'text-jira-blue border-jira-blue bg-blue-50'
                  : 'text-jira-gray-600 hover:text-jira-gray-800 border-transparent hover:bg-jira-gray-50'
              }`}
            >
              <ClipboardList size={18} />
              Issues
              <span className="bg-jira-gray-200 text-jira-gray-700 px-2 py-0.5 rounded-full text-xs">
                {issues.length}
              </span>
            </button>
            <button
              onClick={() => setActiveTab('automation')}
              className={`flex items-center gap-2 px-6 py-4 font-medium transition-all border-b-2 ${
                activeTab === 'automation'
                  ? 'text-jira-blue border-jira-blue bg-blue-50'
                  : 'text-jira-gray-600 hover:text-jira-gray-800 border-transparent hover:bg-jira-gray-50'
              }`}
            >
              <Sparkles size={18} />
              AI Automation
              {automationResult && (
                <span className="bg-jira-green text-white px-2 py-0.5 rounded-full text-xs">
                  ✓
                </span>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-6 pb-8">
        <AnimatePresence mode="wait">
          {activeTab === 'issues' ? (
            <motion.div
              key="issues"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="grid grid-cols-1 lg:grid-cols-2 gap-6 bg-white rounded-b-lg rounded-tr-lg shadow-jira overflow-hidden"
            >
              {/* Issues List */}
              <div className="p-6 border-r border-jira-gray-200">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-jira-gray-900">All Issues</h2>
                  <div className="text-sm text-jira-gray-600">
                    {issues.length} issue{issues.length !== 1 ? 's' : ''}
                  </div>
                </div>
                
                {loading ? (
                  <div className="flex justify-center items-center h-64">
                    <div className="flex flex-col items-center gap-3">
                      <Loader2 className="animate-spin text-jira-blue" size={32} />
                      <span className="text-jira-gray-600 text-sm">Loading issues...</span>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2 max-h-[600px] overflow-y-auto pr-2">
                    {issues.length > 0 ? (
                      issues.map(issue => (
                        <motion.div
                          key={issue.key}
                          whileHover={{ scale: 1.01 }}
                          className="cursor-pointer p-4 bg-jira-gray-50 rounded-lg border border-jira-gray-200 hover:border-jira-blue hover:bg-blue-50 transition-all"
                          onClick={() => fetchIssueDetails(issue.key)}
                        >
                          <div className="flex items-start gap-3">
                            <div className="text-jira-gray-600 mt-1 p-1 bg-white rounded">
                              {getIssuetypeIcon(issue.fields.issuetype)}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="font-mono text-sm font-semibold text-jira-blue">{issue.key}</span>
                                <span className={`jira-status-badge ${getStatusColor(issue.fields.status?.name)}`}>
                                  {issue.fields.status?.name || 'Unknown'}
                                </span>
                              </div>
                              <h3 className="font-medium text-jira-gray-900 text-sm leading-tight mb-2 line-clamp-2">
                                {issue.fields.summary}
                              </h3>
                              <div className="flex items-center gap-2 text-xs text-jira-gray-600">
                                <span>{issue.fields.issuetype?.name}</span>
                                <span>•</span>
                                <span>{issue.fields.assignee?.displayName || 'Unassigned'}</span>
                              </div>
                            </div>
                          </div>
                        </motion.div>
                      ))
                    ) : (
                      <div className="text-center text-jira-gray-500 py-12">
                        <ClipboardList size={48} className="mx-auto mb-3 text-jira-gray-300" />
                        <p className="text-lg font-medium mb-1">No issues found</p>
                        <p className="text-sm">Create your first ticket using AI automation</p>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Issue Details */}
              <div className="p-6">
                <h2 className="text-lg font-semibold mb-4 text-jira-gray-900">Issue Details</h2>
                
                {selectedIssue ? (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="space-y-6"
                  >
                    <div className="border-b border-jira-gray-200 pb-4">
                      <div className="flex items-start gap-3 mb-3">
                        <div className="text-jira-gray-600 p-1 bg-jira-gray-100 rounded">
                          {getIssuetypeIcon(selectedIssue.fields?.issuetype)}
                        </div>
                        <div className="flex-1">
                          <h3 className="text-xl font-bold text-jira-gray-900 mb-1">{selectedIssue.key}</h3>
                          <p className="text-jira-gray-700 leading-relaxed">{selectedIssue.fields?.summary}</p>
                        </div>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        <span className={`jira-status-badge ${getStatusColor(selectedIssue.fields?.status?.name)}`}>
                          {selectedIssue.fields?.status?.name || 'Unknown'}
                        </span>
                        <span className="jira-status-badge bg-jira-gray-100 text-jira-gray-700">
                          {selectedIssue.fields?.issuetype?.name}
                        </span>
                        <span className={`jira-status-badge ${getPriorityColor(selectedIssue.fields?.priority?.name)}`}>
                          {selectedIssue.fields?.priority?.name || 'No priority'}
                        </span>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div className="space-y-3">
                        <div>
                          <span className="block text-jira-gray-600 font-medium mb-1">Assignee</span>
                          <span className="text-jira-gray-900">{selectedIssue.fields?.assignee?.displayName || 'Unassigned'}</span>
                        </div>
                        <div>
                          <span className="block text-jira-gray-600 font-medium mb-1">Reporter</span>
                          <span className="text-jira-gray-900">{selectedIssue.fields?.reporter?.displayName || 'Unknown'}</span>
                        </div>
                      </div>
                      <div className="space-y-3">
                        <div>
                          <span className="block text-jira-gray-600 font-medium mb-1">Created</span>
                          <span className="text-jira-gray-900">{formatDate(selectedIssue.fields?.created)}</span>
                        </div>
                        <div>
                          <span className="block text-jira-gray-600 font-medium mb-1">Updated</span>
                          <span className="text-jira-gray-900">{formatDate(selectedIssue.fields?.updated)}</span>
                        </div>
                      </div>
                    </div>

                    <div>
                      <h4 className="font-semibold text-jira-gray-900 mb-3 flex items-center gap-2">
                        <FileText size={16} />
                        Description
                      </h4>
                      <div className="bg-jira-gray-50 p-4 rounded-lg text-sm border border-jira-gray-200">
                        {adfToText(selectedIssue.fields?.description).trim() ? (
                          <div className="text-jira-gray-700 whitespace-pre-wrap break-words">
                            {adfToText(selectedIssue.fields.description).trim()}
                          </div>
                        ) : (
                          <em className="text-jira-gray-500">No description provided</em>
                        )}
                      </div>
                    </div>
                  </motion.div>
                ) : (
                  <div className="text-center text-jira-gray-500 py-12">
                    <div className="w-16 h-16 bg-jira-gray-100 rounded-lg flex items-center justify-center mx-auto mb-3">
                      <FileText size={24} className="text-jira-gray-400" />
                    </div>
                    <p className="text-lg font-medium mb-1">Select an issue</p>
                    <p className="text-sm">Click on any issue from the list to view its details</p>
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
              className="space-y-6"
            >
              {/* Automation Input */}
              <div className="jira-card p-6">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 bg-gradient-to-r from-jira-blue to-jira-blue-light rounded-lg flex items-center justify-center">
                    <Sparkles className="text-white" size={20} />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-jira-gray-900">AI-Powered Ticket Generation</h2>
                    <p className="text-sm text-jira-gray-600">Describe your requirements and let AI create structured tickets</p>
                  </div>
                </div>
                
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-jira-gray-700 mb-2">
                      Project Requirement *
                    </label>
                    <textarea
                      value={requirement}
                      onChange={(e) => setRequirement(e.target.value)}
                      maxLength={2000}
                      className="w-full px-4 py-3 border border-jira-gray-300 rounded-lg focus:ring-2 focus:ring-jira-blue focus:border-jira-blue transition-colors text-jira-gray-900 placeholder-jira-gray-500"
                      rows="4"
                      placeholder="Example: Build a user authentication system with email verification, password reset functionality, and OAuth integration for Google and GitHub..."
                    />
                    <div className="flex justify-between items-center mt-2">
                      <span className="text-xs text-jira-gray-500">Be as detailed as possible for better results</span>
                      <span className="text-xs text-jira-gray-500">{requirement.length}/2000</span>
                    </div>
                  </div>
                  
                  <button
                    onClick={runAutomation}
                    disabled={automationLoading || !requirement.trim()}
                    className={`w-full py-3 px-6 rounded-lg font-medium transition-all flex items-center justify-center gap-3 ${
                      automationLoading || !requirement.trim()
                        ? 'bg-jira-gray-200 text-jira-gray-500 cursor-not-allowed'
                        : 'jira-button-primary hover:shadow-jira-lg transform hover:scale-[1.01]'
                    }`}
                  >
                    {automationLoading ? (
                      <>
                        <Loader2 className="animate-spin" size={20} />
                        <span>Analyzing requirements & generating tickets...</span>
                      </>
                    ) : (
                      <>
                        <PlusCircle size={20} />
                        <span>Generate Development Tickets & Test Cases</span>
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
                                        <span className={`px-2 py-0.5 text-xs rounded-full ${getPriorityColor(testCase.priority)}`}>
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