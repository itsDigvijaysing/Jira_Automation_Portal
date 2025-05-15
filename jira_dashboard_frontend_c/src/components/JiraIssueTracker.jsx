import React, { useState, useEffect } from 'react';
import { Loader2, Bug, ClipboardList, BookOpen, Rocket } from 'lucide-react';
import { motion } from 'framer-motion';

const JiraIssueTracker = () => {
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedIssue, setSelectedIssue] = useState(null);

  useEffect(() => {
    fetchIssues();
  }, []);


  

  const fetchIssues = async () => {
    try {
      setLoading(true);
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
      default: return <ClipboardList size={20} />;
    }
  };

  return (
    <div className="min-h-screen p-8 bg-gradient-to-tr from-purple-100 via-white to-blue-100">
      <h1 className="text-4xl font-bold text-center mb-10 text-gray-800">🚀 Jira Issue Tracker</h1>

      {error && (
        <div className="bg-red-200 text-red-800 p-4 rounded-xl mb-6 text-center shadow-lg">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Issues List */}
        <div className="bg-white p-6 rounded-3xl shadow-2xl hover:shadow-3xl transition-all duration-300">
          <h2 className="text-2xl font-semibold mb-6 text-gray-700 border-b pb-2">Issues</h2>

          {loading ? (
            <div className="flex justify-center items-center h-40">
              <Loader2 className="animate-spin text-gray-400" size={40} />
            </div>
          ) : (
            <div className="space-y-4 overflow-y-auto max-h-[70vh] pr-2">
              {issues.length > 0 ? (
                issues.map(issue => (
                  <motion.div
                    key={issue.key}
                    whileHover={{ scale: 1.03 }}
                    className="cursor-pointer p-4 bg-gray-50 rounded-2xl border hover:border-blue-400 transition"
                    onClick={() => fetchIssueDetails(issue.key)}
                  >
                    <div className="flex items-start space-x-3">
                      <div className="text-blue-500">{getIssuetypeIcon(issue.fields.issuetype)}</div>
                      <div className="flex-1">
                        <h3 className="font-bold text-lg">{issue.key}: {issue.fields.summary}</h3>
                        <div className="flex flex-wrap gap-2 mt-2 text-sm">
                          <span className={`px-2 py-1 rounded-full ${getStatusColor(issue.fields.status?.name)}`}>
                            {issue.fields.status?.name || 'Unknown'}
                          </span>
                          <span className="text-gray-500">
                            {issue.fields.assignee ? `Assigned to: ${issue.fields.assignee.displayName}` : 'Unassigned'}
                          </span>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                ))
              ) : (
                <div className="text-center text-gray-400">No issues found</div>
              )}
            </div>
          )}
        </div>

        {/* Issue Details */}
        <div className="bg-white p-6 rounded-3xl shadow-2xl hover:shadow-3xl transition-all duration-300">
          <h2 className="text-2xl font-semibold mb-6 text-gray-700 border-b pb-2">Issue Details</h2>

          {selectedIssue ? (
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-4"
            >
              <h3 className="text-xl font-bold">{selectedIssue.key}: {selectedIssue.fields?.summary}</h3>

              <div>
                <span className={`px-3 py-1 rounded-full text-sm ${getStatusColor(selectedIssue.fields?.status?.name)}`}>
                  {selectedIssue.fields?.status?.name || 'Unknown'}
                </span>
              </div>

              <div className="bg-gray-100 p-4 rounded-xl space-y-2">
                <div><strong>Type:</strong> {selectedIssue.fields?.issuetype?.name}</div>
                <div><strong>Priority:</strong> {selectedIssue.fields?.priority?.name || 'Not set'}</div>
                <div><strong>Assignee:</strong> {selectedIssue.fields?.assignee?.displayName || 'Unassigned'}</div>
                <div><strong>Created:</strong> {new Date(selectedIssue.fields?.created).toLocaleDateString()}</div>
              </div>

              <div>
                <h4 className="font-semibold">Description:</h4>
                <div className="mt-2 p-3 bg-gray-50 rounded-lg">
                  {selectedIssue.fields?.description ? (
                    <div dangerouslySetInnerHTML={{ 
                      __html: typeof selectedIssue.fields.description === 'object' 
                        ? 'Complex formatting (ADF)' 
                        : selectedIssue.fields.description 
                    }} />
                  ) : (
                    <em className="text-gray-400">No description provided</em>
                  )}
                </div>
              </div>
            </motion.div>
          ) : (
            <div className="text-center text-gray-400">ALL Jira Content</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default JiraIssueTracker;
