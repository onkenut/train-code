import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Play, Pause, Square, Loader, CheckCircle, XCircle, Clock, Terminal, RefreshCw } from 'lucide-react';
import { executions } from '../api';

function ExecutionDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [execution, setExecution] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [nodeStatuses, setNodeStatuses] = useState({});
  const logsEndRef = useRef(null);
  const wsRef = useRef(null);

  useEffect(() => {
    loadData();
    setupWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [id]);

  const loadData = async () => {
    try {
      const [execRes, logsRes] = await Promise.all([
        executions.get(id),
        executions.getLogs(id)
      ]);
      setExecution(execRes.data);
      setLogs(logsRes.data);

      const statuses = {};
      logsRes.data.forEach(log => {
        statuses[log.node_id] = log.status;
      });
      setNodeStatuses(statuses);
    } catch (error) {
      console.error('Failed to load execution:', error);
    } finally {
      setLoading(false);
    }
  };

  const setupWebSocket = () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      ws.send(JSON.stringify({
        type: 'subscribe',
        executionId: id
      }));
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      handleWebSocketMessage(message);
    };

    ws.onclose = () => {
      setTimeout(() => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) {
          setupWebSocket();
        }
      }, 3000);
    };

    wsRef.current = ws;
  };

  const handleWebSocketMessage = (message) => {
    const { event, data } = message;

    if (data.executionId !== id) return;

    switch (event) {
      case 'execution:start':
        setExecution(prev => prev ? { ...prev, status: 'running' } : prev);
        break;
      case 'execution:complete':
        setExecution(prev => prev ? { ...prev, status: 'completed', finished_at: data.timestamp } : prev);
        loadData();
        break;
      case 'execution:fail':
        setExecution(prev => prev ? { ...prev, status: 'failed', finished_at: data.timestamp } : prev);
        loadData();
        break;
      case 'execution:pause':
        setExecution(prev => prev ? { ...prev, status: 'paused' } : prev);
        break;
      case 'execution:resume':
        setExecution(prev => prev ? { ...prev, status: 'running' } : prev);
        break;
      case 'execution:terminate':
        setExecution(prev => prev ? { ...prev, status: 'terminated', finished_at: data.timestamp } : prev);
        break;

      case 'node:start':
        setNodeStatuses(prev => ({ ...prev, [data.nodeId]: 'running' }));
        break;
      case 'node:complete':
        setNodeStatuses(prev => ({ ...prev, [data.nodeId]: 'completed' }));
        addLog({
          node_id: data.nodeId,
          status: 'completed',
          output_data: data.output,
          started_at: data.timestamp
        });
        break;
      case 'node:error':
        setNodeStatuses(prev => ({ ...prev, [data.nodeId]: 'failed' }));
        addLog({
          node_id: data.nodeId,
          status: 'failed',
          error_msg: data.error,
          started_at: data.timestamp
        });
        break;
      case 'node:skip':
        setNodeStatuses(prev => ({ ...prev, [data.nodeId]: 'skipped' }));
        addLog({
          node_id: data.nodeId,
          status: 'skipped',
          error_msg: data.reason,
          started_at: data.timestamp
        });
        break;
    }
  };

  const addLog = (log) => {
    setLogs(prev => [...prev, { ...log, id: Date.now() }]);
  };

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handlePause = async () => {
    try {
      await executions.pause(id);
    } catch (error) {
      alert('暂停失败');
    }
  };

  const handleResume = async () => {
    try {
      await executions.resume(id);
    } catch (error) {
      alert('恢复失败');
    }
  };

  const handleTerminate = async () => {
    if (confirm('确定要终止这个执行吗？')) {
      try {
        await executions.terminate(id);
      } catch (error) {
        alert('终止失败');
      }
    }
  };

  const getStatusConfig = (status) => {
    const configs = {
      pending: { label: '等待中', color: '#94a3b8', bg: '#475569', icon: Clock },
      running: { label: '运行中', color: '#facc15', bg: '#ca8a04', icon: Loader },
      completed: { label: '已完成', color: '#4ade80', bg: '#16a34a', icon: CheckCircle },
      failed: { label: '失败', color: '#f87171', bg: '#dc2626', icon: XCircle },
      paused: { label: '已暂停', color: '#fb923c', bg: '#ea580c', icon: Pause },
      terminated: { label: '已终止', color: '#f87171', bg: '#dc2626', icon: Square }
    };
    return configs[status] || configs.pending;
  };

  const getNodeStatusStyle = (status) => {
    const styles = {
      pending: { color: '#94a3b8', bg: '#334155' },
      running: { color: '#facc15', bg: 'rgba(202, 138, 4, 0.3)' },
      completed: { color: '#4ade80', bg: 'rgba(22, 163, 74, 0.3)' },
      failed: { color: '#f87171', bg: 'rgba(220, 38, 38, 0.3)' },
      skipped: { color: '#9ca3af', bg: '#1f2937' }
    };
    return styles[status] || styles.pending;
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

  const status = getStatusConfig(execution?.status);
  const StatusIcon = status.icon;

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      backgroundColor: '#0f172a'
    }}>
      <div style={{
        height: '56px',
        backgroundColor: '#1e293b',
        borderBottom: '1px solid #334155',
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        gap: '16px',
        flexShrink: 0
      }}>
        <button
          onClick={() => navigate(-1)}
          style={{
            padding: '8px',
            backgroundColor: 'transparent',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            color: '#94a3b8'
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.backgroundColor = '#334155';
            e.currentTarget.style.color = '#ffffff';
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent';
            e.currentTarget.style.color = '#94a3b8';
          }}
        >
          <ArrowLeft size={20} />
        </button>

        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 style={{
            color: '#ffffff',
            fontWeight: 500,
            margin: 0,
            fontSize: '16px',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis'
          }}>
            执行详情: {execution?.workflow_name || '未知工作流'}
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: status.color }}>
              <StatusIcon size={12} style={{
                animation: execution?.status === 'running' ? 'spin 1s linear infinite' : 'none'
              }} />
              {status.label}
            </span>
            <span style={{ color: '#475569' }}>|</span>
            <span style={{ color: '#64748b' }}>ID: {execution?.id?.slice(0, 8)}...</span>
          </div>
        </div>

        {execution?.status === 'running' && (
          <>
            <button
              onClick={handlePause}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 12px',
                backgroundColor: 'rgba(202, 138, 4, 0.2)',
                color: '#facc15',
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer',
                fontSize: '14px'
              }}
              onMouseOver={(e) => { e.currentTarget.style.backgroundColor = 'rgba(202, 138, 4, 0.3)'; }}
              onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'rgba(202, 138, 4, 0.2)'; }}
            >
              <Pause size={16} />
              暂停
            </button>
            <button
              onClick={handleTerminate}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 12px',
                backgroundColor: 'rgba(220, 38, 38, 0.2)',
                color: '#f87171',
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer',
                fontSize: '14px'
              }}
              onMouseOver={(e) => { e.currentTarget.style.backgroundColor = 'rgba(220, 38, 38, 0.3)'; }}
              onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'rgba(220, 38, 38, 0.2)'; }}
            >
              <Square size={16} />
              终止
            </button>
          </>
        )}

        {execution?.status === 'paused' && (
          <button
            onClick={handleResume}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '6px 12px',
              backgroundColor: 'rgba(22, 163, 74, 0.2)',
              color: '#4ade80',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '14px'
            }}
            onMouseOver={(e) => { e.currentTarget.style.backgroundColor = 'rgba(22, 163, 74, 0.3)'; }}
            onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'rgba(22, 163, 74, 0.2)'; }}
          >
            <Play size={16} />
            恢复
          </button>
        )}

        <button
          onClick={loadData}
          style={{
            padding: '8px',
            backgroundColor: 'transparent',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            color: '#94a3b8'
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.backgroundColor = '#334155';
            e.currentTarget.style.color = '#ffffff';
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent';
            e.currentTarget.style.color = '#94a3b8';
          }}
          title="刷新"
        >
          <RefreshCw size={18} />
        </button>
      </div>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <div style={{
            padding: '16px',
            borderBottom: '1px solid #334155',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Terminal size={18} style={{ color: '#94a3b8' }} />
            <h2 style={{ color: '#ffffff', fontWeight: 500, margin: 0, fontSize: '16px' }}>执行日志</h2>
            <span style={{ fontSize: '12px', color: '#64748b' }}>({logs.length} 条)</span>
          </div>

          <div style={{
            flex: 1,
            overflowY: 'auto',
            backgroundColor: '#020617',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
            fontSize: '14px'
          }}>
            {logs.length === 0 ? (
              <div style={{
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#64748b'
              }}>
                暂无日志
              </div>
            ) : (
              <div style={{ padding: '16px' }}>
                {logs.map((log, index) => {
                  const ns = getNodeStatusStyle(log.status);
                  return (
                    <div
                      key={log.id || index}
                      style={{
                        padding: '12px',
                        borderRadius: '6px',
                        border: '1px solid #334155',
                        backgroundColor: ns.bg,
                        marginBottom: '8px'
                      }}
                    >
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        marginBottom: '8px'
                      }}>
                        <span style={{
                          fontSize: '12px',
                          fontWeight: 500,
                          color: ns.color
                        }}>
                          [{log.status?.toUpperCase()}]
                        </span>
                        <span style={{
                          color: '#94a3b8',
                          fontSize: '12px'
                        }}>
                          {log.node_id}
                        </span>
                        <span style={{
                          color: '#475569',
                          fontSize: '12px'
                        }}>
                          {new Date(log.started_at || Date.now()).toLocaleTimeString()}
                        </span>
                      </div>
                      {log.error_msg && (
                        <div style={{
                          color: '#f87171',
                          fontSize: '12px',
                          marginBottom: '8px'
                        }}>
                          错误: {log.error_msg}
                        </div>
                      )}
                      {log.output_data && (
                        <pre style={{
                          color: '#cbd5e1',
                          fontSize: '12px',
                          overflowX: 'auto',
                          whiteSpace: 'pre-wrap',
                          margin: 0
                        }}>
                          {typeof log.output_data === 'string'
                            ? log.output_data
                            : JSON.stringify(log.output_data, null, 2)}
                        </pre>
                      )}
                    </div>
                  );
                })}
                <div ref={logsEndRef} />
              </div>
            )}
          </div>
        </div>

        <div style={{
          width: '288px',
          backgroundColor: '#1e293b',
          borderLeft: '1px solid #334155',
          overflowY: 'auto',
          flexShrink: 0
        }}>
          <div style={{
            padding: '16px',
            borderBottom: '1px solid #334155'
          }}>
            <h3 style={{
              color: '#ffffff',
              fontWeight: 500,
              margin: '0 0 4px 0',
              fontSize: '16px'
            }}>节点状态</h3>
            <p style={{
              fontSize: '12px',
              color: '#94a3b8',
              margin: 0
            }}>点击节点查看详情</p>
          </div>

          <div style={{ padding: '12px' }}>
            {Object.entries(nodeStatuses).map(([nodeId, status]) => {
              const ns = getNodeStatusStyle(status);
              return (
                <div
                  key={nodeId}
                  style={{
                    padding: '8px',
                    borderRadius: '6px',
                    border: '1px solid #334155',
                    backgroundColor: ns.bg,
                    marginBottom: '8px'
                  }}
                >
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between'
                  }}>
                    <span style={{
                      fontSize: '14px',
                      color: '#ffffff',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis'
                    }}>{nodeId}</span>
                    <span style={{
                      fontSize: '12px',
                      color: ns.color,
                      textTransform: 'capitalize'
                    }}>
                      {status}
                    </span>
                  </div>
                </div>
              );
            })}
            {Object.keys(nodeStatuses).length === 0 && (
              <div style={{
                textAlign: 'center',
                color: '#64748b',
                fontSize: '14px',
                padding: '16px 0'
              }}>
                暂无节点数据
              </div>
            )}
          </div>

          <div style={{
            padding: '16px',
            borderTop: '1px solid #334155',
            marginTop: '16px'
          }}>
            <h3 style={{
              color: '#ffffff',
              fontWeight: 500,
              margin: '0 0 12px 0',
              fontSize: '16px'
            }}>执行信息</h3>
            <div style={{ fontSize: '14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ color: '#94a3b8' }}>触发方式</span>
                <span style={{ color: '#ffffff' }}>{execution?.trigger_type}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ color: '#94a3b8' }}>开始时间</span>
                <span style={{ color: '#ffffff', fontSize: '12px' }}>
                  {execution?.started_at ? new Date(execution.started_at).toLocaleString() : '-'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#94a3b8' }}>结束时间</span>
                <span style={{ color: '#ffffff', fontSize: '12px' }}>
                  {execution?.finished_at ? new Date(execution.finished_at).toLocaleString() : '-'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ExecutionDetail;
