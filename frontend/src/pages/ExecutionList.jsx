import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Play, Clock, CheckCircle, XCircle, Pause, Square, Eye, RefreshCw, List, ArrowRight } from 'lucide-react';
import { executions } from '../api';

function ExecutionList() {
  const navigate = useNavigate();
  const [executionList, setExecutionList] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadExecutions();
  }, []);

  const loadExecutions = async () => {
    try {
      setLoading(true);
      const res = await executions.list();
      setExecutionList(res.data);
    } catch (error) {
      console.error('Failed to load executions:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusConfig = (status) => {
    const configs = {
      pending: { label: '等待中', color: '#94a3b8', bg: 'rgba(71, 85, 105, 0.3)', icon: Clock },
      running: { label: '运行中', color: '#facc15', bg: 'rgba(202, 138, 4, 0.2)', icon: Play },
      completed: { label: '已完成', color: '#4ade80', bg: 'rgba(22, 163, 74, 0.2)', icon: CheckCircle },
      failed: { label: '失败', color: '#f87171', bg: 'rgba(220, 38, 38, 0.2)', icon: XCircle },
      paused: { label: '已暂停', color: '#fb923c', bg: 'rgba(234, 88, 12, 0.2)', icon: Pause },
      terminated: { label: '已终止', color: '#f87171', bg: 'rgba(220, 38, 38, 0.2)', icon: Square }
    };
    return configs[status] || configs.pending;
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString();
  };

  const formatDuration = (started, finished) => {
    if (!started || !finished) return '-';
    const start = new Date(started).getTime();
    const end = new Date(finished).getTime();
    const duration = end - start;
    
    if (duration < 1000) return `${duration}ms`;
    if (duration < 60000) return `${(duration / 1000).toFixed(1)}s`;
    if (duration < 3600000) return `${(duration / 60000).toFixed(1)}m`;
    return `${(duration / 3600000).toFixed(1)}h`;
  };

  if (loading) {
    return (
      <div style={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#0f172a'
      }}>
        <RefreshCw size={32} style={{ color: '#818cf8', animation: 'spin 1s linear infinite' }} />
      </div>
    );
  }

  return (
    <div style={{ height: '100%', backgroundColor: '#0f172a', overflow: 'auto' }}>
      <div style={{ maxWidth: '72rem', margin: '0 auto', padding: '32px' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '32px'
        }}>
          <div>
            <h1 style={{
              fontSize: '30px',
              fontWeight: 700,
              color: '#ffffff',
              marginBottom: '8px'
            }}>执行历史</h1>
            <p style={{ color: '#94a3b8', margin: 0 }}>查看所有工作流的执行记录和日志</p>
          </div>
          <button
            onClick={loadExecutions}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 20px',
              backgroundColor: '#1e293b',
              color: '#e2e8f0',
              borderRadius: '8px',
              border: '1px solid #334155',
              cursor: 'pointer',
              fontSize: '14px'
            }}
            onMouseOver={(e) => { e.currentTarget.style.backgroundColor = '#334155'; }}
            onMouseOut={(e) => { e.currentTarget.style.backgroundColor = '#1e293b'; }}
          >
            <RefreshCw size={18} />
            刷新
          </button>
        </div>

        {executionList.length === 0 ? (
          <div style={{
            textAlign: 'center',
            padding: '64px 0',
            backgroundColor: 'rgba(30, 41, 59, 0.5)',
            borderRadius: '12px',
            border: '1px solid #334155'
          }}>
            <div style={{
              width: '64px',
              height: '64px',
              margin: '0 auto 16px',
              borderRadius: '50%',
              backgroundColor: '#334155',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <List size={32} style={{ color: '#64748b' }} />
            </div>
            <h3 style={{
              fontSize: '20px',
              fontWeight: 600,
              color: '#ffffff',
              marginBottom: '8px'
            }}>暂无执行记录</h3>
            <p style={{ color: '#94a3b8', marginBottom: '24px' }}>执行工作流后将在这里显示记录</p>
            <button
              onClick={() => navigate('/')}
              style={{
                padding: '8px 24px',
                backgroundColor: '#4f46e5',
                color: '#ffffff',
                borderRadius: '8px',
                border: 'none',
                cursor: 'pointer'
              }}
              onMouseOver={(e) => { e.currentTarget.style.backgroundColor = '#4338ca'; }}
              onMouseOut={(e) => { e.currentTarget.style.backgroundColor = '#4f46e5'; }}
            >
              前往工作流
            </button>
          </div>
        ) : (
          <div style={{
            backgroundColor: '#1e293b',
            borderRadius: '12px',
            border: '1px solid #334155',
            overflow: 'hidden'
          }}>
            <div style={{
              display: 'grid',
              gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr auto',
              padding: '12px 16px',
              backgroundColor: '#0f172a',
              borderBottom: '1px solid #334155',
              fontSize: '12px',
              fontWeight: 600,
              color: '#94a3b8',
              textTransform: 'uppercase',
              letterSpacing: '0.05em'
            }}>
              <div>工作流</div>
              <div>状态</div>
              <div>触发方式</div>
              <div>开始时间</div>
              <div>耗时</div>
              <div>操作</div>
            </div>

            {executionList.map((exec) => {
              const status = getStatusConfig(exec.status);
              const StatusIcon = status.icon;
              return (
                <div
                  key={exec.id}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr auto',
                    padding: '14px 16px',
                    borderBottom: '1px solid #334155',
                    alignItems: 'center',
                    cursor: 'pointer'
                  }}
                  onClick={() => navigate(`/execution/${exec.id}`)}
                  onMouseOver={(e) => { e.currentTarget.style.backgroundColor = 'rgba(99, 102, 241, 0.1)'; }}
                  onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
                >
                  <div>
                    <div style={{
                      color: '#ffffff',
                      fontSize: '14px',
                      fontWeight: 500,
                      marginBottom: '2px'
                    }}>
                      {exec.workflow_name || '未知工作流'}
                    </div>
                    <div style={{
                      color: '#64748b',
                      fontSize: '12px',
                      fontFamily: 'monospace'
                    }}>
                      {exec.id.slice(0, 12)}...
                    </div>
                  </div>

                  <div>
                    <span style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '4px 10px',
                      borderRadius: '9999px',
                      backgroundColor: status.bg,
                      color: status.color,
                      fontSize: '12px',
                      fontWeight: 500
                    }}>
                      <StatusIcon size={12} style={{
                        animation: exec.status === 'running' ? 'spin 1s linear infinite' : 'none'
                      }} />
                      {status.label}
                    </span>
                  </div>

                  <div style={{
                    color: '#e2e8f0',
                    fontSize: '14px',
                    textTransform: 'capitalize'
                  }}>
                    {exec.trigger_type}
                  </div>

                  <div style={{
                    color: '#94a3b8',
                    fontSize: '12px'
                  }}>
                    {formatDate(exec.started_at)}
                  </div>

                  <div style={{
                    color: '#94a3b8',
                    fontSize: '12px',
                    fontFamily: 'monospace'
                  }}>
                    {formatDuration(exec.started_at, exec.finished_at)}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/execution/${exec.id}`);
                      }}
                      style={{
                        padding: '6px',
                        backgroundColor: 'transparent',
                        border: 'none',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        color: '#818cf8'
                      }}
                      onMouseOver={(e) => { e.currentTarget.style.backgroundColor = 'rgba(99, 102, 241, 0.2)'; }}
                      onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
                      title="查看详情"
                    >
                      <Eye size={16} />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/workflow/${exec.workflow_id}`);
                      }}
                      style={{
                        padding: '6px',
                        backgroundColor: 'transparent',
                        border: 'none',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        color: '#94a3b8'
                      }}
                      onMouseOver={(e) => {
                        e.currentTarget.style.backgroundColor = 'rgba(148, 163, 184, 0.2)';
                        e.currentTarget.style.color = '#e2e8f0';
                      }}
                      onMouseOut={(e) => {
                        e.currentTarget.style.backgroundColor = 'transparent';
                        e.currentTarget.style.color = '#94a3b8';
                      }}
                      title="打开工作流"
                    >
                      <ArrowRight size={16} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default ExecutionList;
