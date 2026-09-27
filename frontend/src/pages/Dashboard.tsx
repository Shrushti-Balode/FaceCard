import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/hooks/useAuth";
import { useBusSimulation } from "@/hooks/useBusSimulation";
import { getJourneys, getTransactions, getUserById } from "@/utils/storage";
import { Bus, Play, Pause, MapPin, Clock, CreditCard, TrendingUp } from "lucide-react";
import { format } from "date-fns";

const Dashboard = () => {
  const { user, updateUser } = useAuth();
  const { currentStopName, isRunning, toggleSimulation, stops, stopIndex } = useBusSimulation();
  
  const [journeys, setJourneys] = useState<any[]>([]);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user) {
      Promise.all([
        getUserById(user.id),
        getJourneys(user.id),
        getTransactions(user.id)
      ]).then(([freshUser, j, t]) => {
        updateUser(freshUser);
        setJourneys(j);
        setTransactions(t);
      }).catch(console.error).finally(() => setLoading(false));
    }
  }, [user?.id, updateUser]);

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-muted/30">
        <Card><CardContent className="p-8"><p>Please log in.</p></CardContent></Card>
      </div>
    );
  }

  const progress = ((stopIndex + 1) / stops.length) * 100;

  return (
    <div className="min-h-screen bg-muted/30 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Welcome back, {user.name || user.firstName}!</h1>
          <p className="text-muted-foreground mt-2">Manage your journeys, track buses, and monitor wallet balance.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center gap-4">
                <div className="bg-primary/10 p-3 rounded-lg"><CreditCard className="h-6 w-6 text-primary" /></div>
                <div><p className="text-sm text-muted-foreground">Wallet Balance</p><h3 className="text-2xl font-bold">₹{user.wallet}</h3></div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center gap-4">
                <div className="bg-secondary/10 p-3 rounded-lg"><TrendingUp className="h-6 w-6 text-secondary" /></div>
                <div><p className="text-sm text-muted-foreground">Total Journeys</p><h3 className="text-2xl font-bold">{journeys.length}</h3></div>
              </div>
            </CardContent>
          </Card>
          <Card className="md:col-span-2">
            <CardContent className="p-6">
              <div className="flex items-center justify-between h-full">
                <div>
                  <p className="text-sm text-muted-foreground mb-1">Face Card ID</p>
                  <div className="flex items-center gap-2"><h3 className="text-xl font-mono font-bold tracking-wider">{user.id}</h3><Badge variant="outline" className="bg-green-50 text-green-700">Active</Badge></div>
                </div>
                <div className="text-right">
                  <p className="text-sm text-muted-foreground mb-1">Registered Route</p>
                  <h3 className="text-lg font-medium">{user.route}</h3>
                  <p className="text-xs text-muted-foreground">{user.pickup} → {user.drop}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <Tabs defaultValue="tracker" className="w-full">
          <TabsList className="mb-6"><TabsTrigger value="tracker">Live Tracker</TabsTrigger><TabsTrigger value="history">Journey History</TabsTrigger><TabsTrigger value="wallet">Wallet & Transactions</TabsTrigger></TabsList>
          
          <TabsContent value="tracker" className="space-y-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between"><CardTitle>Live Bus Simulation</CardTitle><Button variant={isRunning ? "secondary" : "default"} onClick={toggleSimulation}>{isRunning ? <><Pause className="mr-2 h-4 w-4" /> Pause Simulation</> : <><Play className="mr-2 h-4 w-4" /> Start Simulation</>}</Button></CardHeader>
              <CardContent>
                <div className="relative pt-8 pb-4">
                  <Progress value={progress} className="h-2 mb-8" />
                  <div className="absolute top-4 w-full flex justify-between px-2">
                    {stops.map((stop, i) => (
                      <div key={stop} className="flex flex-col items-center" style={{ width: '0' }}>
                        <div className={`h-4 w-4 rounded-full border-2 bg-background z-10 ${i <= stopIndex ? 'border-primary bg-primary' : 'border-muted'}`} />
                        <span className={`text-xs mt-2 font-medium whitespace-nowrap absolute -bottom-6 ${i === stopIndex ? 'text-primary' : 'text-muted-foreground'}`}>{stop}</span>
                      </div>
                    ))}
                  </div>
                  <div className="absolute top-0 transition-all duration-1000 ease-in-out z-20" style={{ left: `calc(${progress}% - 12px)` }}>
                    <div className="bg-primary text-primary-foreground p-1.5 rounded-full shadow-lg"><Bus className="h-5 w-5" /></div>
                  </div>
                </div>
                <div className="mt-12 p-4 bg-muted/50 rounded-lg flex items-center justify-between">
                  <div className="flex items-center gap-3"><MapPin className="h-5 w-5 text-primary" /><div><p className="text-sm text-muted-foreground">Current Stop</p><p className="font-semibold text-lg">{currentStopName}</p></div></div>
                  <div className="flex items-center gap-3"><Clock className="h-5 w-5 text-secondary" /><div><p className="text-sm text-muted-foreground">Status</p><p className="font-semibold">{isRunning ? 'In Transit' : 'Stopped'}</p></div></div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="history">
            <Card><CardHeader><CardTitle>Recent Journeys</CardTitle></CardHeader><CardContent>
              {loading ? <p>Loading...</p> : journeys.length === 0 ? <p className="text-muted-foreground">No journeys yet.</p> : (
                <div className="space-y-4">
                  {journeys.map((j) => (
                    <div key={j.journey_id} className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
                      <div><p className="font-semibold">{j.boarding_stop} → {j.exit_stop || "In Progress"}</p><p className="text-sm text-muted-foreground">{new Date(j.started_at).toLocaleString()}</p></div>
                      <div className="text-right"><Badge variant={j.status === 'completed' ? "default" : "secondary"}>{j.status}</Badge>{j.fare > 0 && <p className="text-sm font-medium mt-1">₹{j.fare}</p>}</div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent></Card>
          </TabsContent>

          <TabsContent value="wallet">
            <Card><CardHeader><CardTitle>Transaction History</CardTitle></CardHeader><CardContent>
              {loading ? <p>Loading...</p> : transactions.length === 0 ? <p className="text-muted-foreground">No transactions yet.</p> : (
                <div className="space-y-4">
                  {transactions.map((t) => (
                    <div key={t.transaction_id} className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
                      <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-full ${t.type === 'wallet_load' ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'}`}>
                          {t.type === 'wallet_load' ? <TrendingUp className="h-4 w-4" /> : <Bus className="h-4 w-4" />}
                        </div>
                        <div><p className="font-medium">{t.description}</p><p className="text-sm text-muted-foreground">{new Date(t.timestamp).toLocaleString()}</p></div>
                      </div>
                      <div className="text-right">
                        <p className={`font-bold ${t.type === 'wallet_load' ? 'text-green-600' : 'text-red-600'}`}>{t.type === 'wallet_load' ? '+' : '-'}₹{t.amount}</p>
                        <p className="text-xs text-muted-foreground">Bal: ₹{t.balance_after}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent></Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};
export default Dashboard;