import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Play, Edit3, Trash2, Clock, CheckCircle, XCircle, Loader } from 'lucide-react';
import { workflows } from '../api';

function WorkflowList() {
  const navigate = useNavigate();
  const [workflowList, setWorkflowList] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadWorkflows();
  }, []);

  const loadWorkflows = async () => {
    try {
      const res = await workflows.list();
      setWorkflowList(res.data);
    } catch (error) {
      console.error('Failed to load workflows:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id, e) => {
    e.stopPropagation();
    if (confirm('确定要删除这个工作流吗？')) {
      try {
        await workflows.delete(id);
        loadWorkflows();
      } catch (error) {
        alert('删除失败');
      }
    }
  };

  const handleExecute = async (id, e) => {
    e.stopPropagation();
    try {
      const res = await workflows.execute(id);
      navigate(`/execution/${res.data.executionId}`);
    } catch (error) {
      alert('执行失败');
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'running':
        return <Loader size={16} style={{ color: '#facc15', animation: 'spin 1s linear infinite' }} />;
      case 'completed':
        return <CheckCircle size={16} style={{ color: '#4ade80' }} />;
      case 'failed':
        return <XCircle size={16} style={{ color: '#f87171' }} />;
      default:
        return <Clock size={16} style={{ color: '#94a3b8' }} />;
    }
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
        <Loader size={32} style={{ color: '#818cf8', animation: 'spin 1s linear infinite' }} />
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
            }}>工作流管理</h1>
            <p style={{ color: '#94a3b8', margin: 0 }}>管理和运行您的自动化工作流</p>
          </div>
          <button
            onClick={() => navigate('/workflow/new')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 20px',
              backgroundColor: '#4f46e5',
              color: '#ffffff',
              borderRadius: '8px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '14px'
            }}
            onMouseOver={(e) => { e.currentTarget.style.backgroundColor = '#4338ca'; }}
            onMouseOut={(e) => { e.currentTarget.style.backgroundColor = '#4f46e5'; }}
          >
            <Plus size={20} />
            新建工作流
          </button>
        </div>

        {workflowList.length === 0 ? (
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
              <Play size={32} style={{ color: '#64748b' }} />
            </div>
            <h3 style={{
              fontSize: '20px',
              fontWeight: 600,
              color: '#ffffff',
              marginBottom: '8px'
            }}>暂无工作流</h3>
            <p style={{ color: '#94a3b8', marginBottom: '24px' }}>点击上方按钮创建您的第一个工作流</p>
            <button
              onClick={() => navigate('/workflow/new')}
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
              创建工作流
            </button>
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
            gap: '16px'
          }}>
            {workflowList.map(workflow => (
              <div
                key={workflow.id}
                onClick={() => navigate(`/workflow/${workflow.id}`)}
                style={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #334155',
                  borderRadius: '12px',
                  padding: '20px',
                  cursor: 'pointer'
                }}
                onMouseOver={(e) => { e.currentTarget.style.borderColor = '#6366f1'; }}
                onMouseOut={(e) => { e.currentTarget.style.borderColor = '#334155'; }}
              >
                <div style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  marginBottom: '12px'
                }}>
                  <h3 style={{
                    fontSize: '18px',
                    fontWeight: 600,
                    color: '#ffffff',
                    margin: 0,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }}>
                    {workflow.name}
                  </h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    {getStatusIcon(workflow.status)}
                  </div>
                </div>

                <p style={{
                  fontSize: '14px',
                  color: '#94a3b8',
                  marginBottom: '16px',
                  minHeight: '40px'
                }}>
                  {workflow.dsl_json ? '已配置工作流' : '尚未配置'}
                </p>

                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '12px',
                  color: '#64748b'
                }}>
                  <span>创建于 {new Date(workflow.created_at).toLocaleDateString()}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <button
                      onClick={(e) => handleExecute(workflow.id, e)}
                      style={{
                        padding: '6px',
                        backgroundColor: 'transparent',
                        border: 'none',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        color: '#4ade80'
                      }}
                      onMouseOver={(e) => { e.currentTarget.style.backgroundColor = 'rgba(22, 163, 74, 0.2)'; }}
                      onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
                      title="执行"
                    >
                      <Play size={16} />
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); navigate(`/workflow/${workflow.id}`); }}
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
                      title="编辑"
                    >
                      <Edit3 size={16} />
                    </button>
                    <button
                      onClick={(e) => handleDelete(workflow.id, e)}
                      style={{
                        padding: '6px',
                        backgroundColor: 'transparent',
                        border: 'none',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        color: '#f87171'
                      }}
                      onMouseOver={(e) => { e.currentTarget.style.backgroundColor = 'rgba(220, 38, 38, 0.2)'; }}
                      onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
                      title="删除"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default WorkflowList;
