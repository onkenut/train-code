import React from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import { Play, Cpu, List } from 'lucide-react';
import WorkflowList from './pages/WorkflowList';
import WorkflowEditor from './pages/WorkflowEditor';
import ExecutionDetail from './pages/ExecutionDetail';
import ExecutionList from './pages/ExecutionList';

function Navbar() {
  const location = useLocation();

  const navItems = [
    { path: '/', label: '工作流', icon: Play },
    { path: '/executions', label: '执行历史', icon: List },
  ];

  return (
    <div style={{
      height: '48px',
      backgroundColor: '#1e293b',
      borderBottom: '1px solid #334155',
      display: 'flex',
      alignItems: 'center',
      padding: '0 16px'
    }}>
      <Link to="/" style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        marginRight: '32px',
        textDecoration: 'none'
      }}>
        <div style={{
          width: '32px',
          height: '32px',
          background: 'linear-gradient(to bottom right, #6366f1, #9333ea)',
          borderRadius: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          <Cpu size={18} style={{ color: '#ffffff' }} />
        </div>
        <span style={{
          color: '#ffffff',
          fontWeight: 700,
          fontSize: '18px'
        }}>FlowForge</span>
      </Link>

      <nav style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        {navItems.map(item => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path ||
            (item.path !== '/' && location.pathname.startsWith(item.path));
          return (
            <Link
              key={item.path}
              to={item.path}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 12px',
                borderRadius: '6px',
                fontSize: '14px',
                textDecoration: 'none',
                backgroundColor: isActive ? '#4f46e5' : 'transparent',
                color: isActive ? '#ffffff' : '#94a3b8'
              }}
              onMouseOver={(e) => {
                if (!isActive) {
                  e.currentTarget.style.backgroundColor = '#334155';
                  e.currentTarget.style.color = '#ffffff';
                }
              }}
              onMouseOut={(e) => {
                if (!isActive) {
                  e.currentTarget.style.backgroundColor = 'transparent';
                  e.currentTarget.style.color = '#94a3b8';
                }
              }}
            >
              <Icon size={16} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div style={{ flex: 1 }} />

      <div style={{ fontSize: '12px', color: '#64748b' }}>
        本地可视化工作流引擎
      </div>
    </div>
  );
}

function App() {
  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#0f172a' }}>
      <Navbar />
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <Routes>
          <Route path="/" element={<WorkflowList />} />
          <Route path="/workflow/:id" element={<WorkflowEditor />} />
          <Route path="/executions" element={<ExecutionList />} />
          <Route path="/execution/:id" element={<ExecutionDetail />} />
        </Routes>
      </div>
    </div>
  );
}

export default App;
