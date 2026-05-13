import React, { useState, useEffect } from 'react';
import { 
  Activity, 
  Cpu, 
  Database, 
  Settings, 
  AlertCircle, 
  CheckCircle2, 
  Zap,
  Thermometer,
  RotateCw,
  Gauge
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  AreaChart,
  Area
} from 'recharts';

// Mock Data for demonstration
const mockHistory = Array.from({ length: 20 }, (_, i) => ({
  time: i,
  temp: 60 + Math.random() * 10,
  rpm: 1700 + Math.random() * 100,
  vibration: 5 + Math.random() * 2,
}));

const Dashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState('overview');
  const [metrics, setMetrics] = useState({
    temp: 72.5,
    rpm: 1745,
    vibration: 5.2,
    current: 5.5,
    status: 'Operational'
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-blue-500/30">
      {/* Navigation */}
      <nav className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-900/20">
              <Zap className="text-white w-6 h-6" />
            </div>
            <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
              SmartFactory <span className="text-blue-500">OS</span>
            </h1>
          </div>
          
          <div className="flex items-center gap-6">
            <div className="flex bg-slate-800/50 p-1 rounded-lg border border-slate-700">
              {['overview', 'analytics', 'nodes'].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
                    activeTab === tab 
                    ? 'bg-blue-600 text-white shadow-lg' 
                    : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </div>
            <div className="w-px h-6 bg-slate-800" />
            <button className="p-2 text-slate-400 hover:text-white transition-colors">
              <Settings className="w-5 h-5" />
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto p-8 space-y-8">
        {/* Header Section */}
        <div className="flex justify-between items-end">
          <div>
            <h2 className="text-3xl font-bold text-white">System Overview</h2>
            <p className="text-slate-400 mt-1">Real-time monitoring of Production Line A - Motor 01</p>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-green-500/10 border border-green-500/20 rounded-full">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className="text-xs font-semibold text-green-500 uppercase tracking-wider">Live Stream Active</span>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard 
            title="Temperature" 
            value={`${metrics.temp}°C`} 
            icon={<Thermometer className="w-5 h-5" />} 
            color="text-orange-500"
            bg="bg-orange-500/10"
            trend="+0.2"
          />
          <StatCard 
            title="Motor RPM" 
            value={metrics.rpm.toString()} 
            icon={<RotateCw className="w-5 h-5" />} 
            color="text-blue-500"
            bg="bg-blue-500/10"
            trend="-5"
          />
          <StatCard 
            title="Vibration" 
            value={`${metrics.vibration} mm/s`} 
            icon={<Activity className="w-5 h-5" />} 
            color="text-purple-500"
            bg="bg-purple-500/10"
            trend="Stable"
          />
          <StatCard 
            title="Current" 
            value={`${metrics.current} A`} 
            icon={<Gauge className="w-5 h-5" />} 
            color="text-emerald-500"
            bg="bg-emerald-500/10"
            trend="+0.1"
          />
        </div>

        {/* Charts & Status */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm">
              <div className="flex justify-between items-center mb-6">
                <h3 className="font-semibold text-lg flex items-center gap-2">
                  <Activity className="w-5 h-5 text-blue-500" />
                  Telemetry History
                </h3>
                <div className="flex gap-2">
                  <span className="flex items-center gap-1.5 text-xs text-slate-400">
                    <div className="w-2 h-2 rounded-full bg-blue-500" /> RPM
                  </span>
                  <span className="flex items-center gap-1.5 text-xs text-slate-400">
                    <div className="w-2 h-2 rounded-full bg-orange-500" /> Temperature
                  </span>
                </div>
              </div>
              <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={mockHistory}>
                    <defs>
                      <linearGradient id="colorRpm" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                    <XAxis dataKey="time" hide />
                    <YAxis hide />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px' }}
                      itemStyle={{ color: '#fff' }}
                    />
                    <Area type="monotone" dataKey="rpm" stroke="#3b82f6" fillOpacity={1} fill="url(#colorRpm)" strokeWidth={2} />
                    <Line type="monotone" dataKey="temp" stroke="#f97316" strokeWidth={2} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6">
              <h3 className="font-semibold text-lg mb-6 flex items-center gap-2">
                <Cpu className="w-5 h-5 text-emerald-500" />
                Infrastructure Health
              </h3>
              <div className="space-y-4">
                <StatusItem label="Edge Gateway" status="healthy" />
                <StatusItem label="MQTT Broker" status="healthy" />
                <StatusItem label="Kafka Clusters" status="healthy" />
                <StatusItem label="Processor" status="healthy" />
                <StatusItem label="InfluxDB" status="healthy" />
                <StatusItem label="OpenPLC" status="warning" message="Delayed Response" />
              </div>
            </div>

            <div className="bg-gradient-to-br from-blue-600 to-indigo-700 rounded-2xl p-6 shadow-xl shadow-blue-900/20 relative overflow-hidden group">
              <div className="relative z-10">
                <h3 className="text-white font-bold text-lg mb-2">Predictive Alert</h3>
                <p className="text-blue-100 text-sm opacity-90 leading-relaxed">
                  Temperature trending +15% above baseline. Maintenance suggested within 48 hours.
                </p>
                <button className="mt-4 bg-white/20 hover:bg-white/30 backdrop-blur-md text-white text-xs font-bold py-2 px-4 rounded-lg transition-all">
                  Generate Report
                </button>
              </div>
              <div className="absolute top-[-20px] right-[-20px] opacity-10 group-hover:scale-110 transition-transform duration-500">
                <AlertCircle className="w-32 h-32 text-white" />
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

const StatCard = ({ title, value, icon, color, bg, trend }: any) => (
  <motion.div 
    whileHover={{ y: -5 }}
    className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 transition-all hover:bg-slate-800/50"
  >
    <div className="flex justify-between items-start">
      <div className={`p-2.5 ${bg} ${color} rounded-xl`}>
        {icon}
      </div>
      <span className={`text-xs font-medium px-2 py-1 rounded-full ${
        trend.includes('+') ? 'bg-emerald-500/10 text-emerald-500' : 
        trend.includes('-') ? 'bg-orange-500/10 text-orange-500' : 
        'bg-slate-500/10 text-slate-400'
      }`}>
        {trend}
      </span>
    </div>
    <div className="mt-4">
      <p className="text-slate-400 text-sm font-medium">{title}</p>
      <p className="text-2xl font-bold text-white mt-1 tracking-tight">{value}</p>
    </div>
  </motion.div>
);

const StatusItem = ({ label, status, message }: any) => (
  <div className="flex items-center justify-between p-3 rounded-xl bg-slate-800/30 border border-slate-800/50">
    <div className="flex items-center gap-3">
      <div className={`w-2 h-2 rounded-full ${status === 'healthy' ? 'bg-emerald-500' : 'bg-orange-500'}`} />
      <span className="text-sm font-medium text-slate-200">{label}</span>
    </div>
    {message ? (
      <span className="text-[10px] text-orange-500 font-bold uppercase tracking-wider">{message}</span>
    ) : (
      <CheckCircle2 className="w-4 h-4 text-emerald-500" />
    )}
  </div>
);

export default Dashboard;
