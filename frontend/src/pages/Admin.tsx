import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { apiFetch } from "@/utils/storage";
import { Shield, Users, Activity, Map, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

const Admin = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [error, setError] = useState("");
  
  const [users, setUsers] = useState<any[]>([]);
  const [journeys, setJourneys] = useState<any[]>([]);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      setLoading(true);
      Promise.all([
        apiFetch("/users"),
        apiFetch("/journeys"),
        apiFetch("/transactions")
      ]).then(([u, j, t]) => {
        setUsers(u);
        setJourneys(j);
        setTransactions(t);
      }).catch(console.error).finally(() => setLoading(false));
    }
  }, [isAuthenticated]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const data = await apiFetch("/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });
      if (data.status === "success") {
        setIsAuthenticated(true);
        setError("");
      } else {
        setError("Invalid credentials");
      }
    } catch (err: unknown) {
      const status = typeof err === "object" && err !== null && "status" in err ? err.status : undefined;
      setError(status === 401 ? "Invalid credentials" : "Error connecting to server");
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-muted/30">
        <Card className="w-full max-w-md shadow-xl">
          <CardHeader className="text-center space-y-2">
            <div className="flex justify-center"><div className="bg-primary/10 p-3 rounded-full"><Shield className="h-8 w-8 text-primary" /></div></div>
            <CardTitle>Admin Access</CardTitle>
            <CardDescription>Enter credentials to access the admin panel</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-2">
                <Input type="text" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
              </div>
              {error && <p className="text-sm text-red-500 text-center">{error}</p>}
              <Button type="submit" className="w-full">Login</Button>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  const activeUsers = users.filter(u => u.isActive).length;
  const totalRevenue = transactions.filter(t => t.type === 'fare').reduce((sum, t) => sum + t.amount, 0);

  return (
    <div className="min-h-screen bg-muted/30 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center mb-8">
          <div><h1 className="text-3xl font-bold">Admin Dashboard</h1><p className="text-muted-foreground mt-2">System overview and management</p></div>
          <Link to="/admin/gate"><Button variant="default"><Map className="mr-2 h-4 w-4" /> Open Gate View <ArrowRight className="ml-2 h-4 w-4" /></Button></Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <Card><CardContent className="p-6 flex items-center gap-4"><div className="bg-blue-100 p-3 rounded-lg"><Users className="h-6 w-6 text-blue-600" /></div><div><p className="text-sm text-muted-foreground">Total Users</p><h3 className="text-2xl font-bold">{users.length}</h3></div></CardContent></Card>
          <Card><CardContent className="p-6 flex items-center gap-4"><div className="bg-green-100 p-3 rounded-lg"><Activity className="h-6 w-6 text-green-600" /></div><div><p className="text-sm text-muted-foreground">Active Users</p><h3 className="text-2xl font-bold">{activeUsers}</h3></div></CardContent></Card>
          <Card><CardContent className="p-6 flex items-center gap-4"><div className="bg-purple-100 p-3 rounded-lg"><Map className="h-6 w-6 text-purple-600" /></div><div><p className="text-sm text-muted-foreground">Total Revenue</p><h3 className="text-2xl font-bold">₹{totalRevenue}</h3></div></CardContent></Card>
        </div>

        <Tabs defaultValue="users" className="w-full">
          <TabsList className="mb-6"><TabsTrigger value="users">Users</TabsTrigger><TabsTrigger value="journeys">Journeys</TabsTrigger><TabsTrigger value="transactions">Transactions</TabsTrigger></TabsList>
          
          <TabsContent value="users">
            <Card><CardHeader><CardTitle>Registered Users</CardTitle></CardHeader><CardContent>
              {loading ? <p>Loading...</p> : (
                <Table><TableHeader><TableRow><TableHead>Face Card ID</TableHead><TableHead>Name</TableHead><TableHead>Route</TableHead><TableHead>Wallet</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
                <TableBody>
                  {users.map(u => (
                    <TableRow key={u.id}>
                      <TableCell className="font-mono font-medium">{u.id}</TableCell>
                      <TableCell>{u.name || `${u.firstName} ${u.lastName}`}</TableCell>
                      <TableCell>{u.route}</TableCell>
                      <TableCell>₹{u.wallet}</TableCell>
                      <TableCell><Badge variant={u.isActive ? "default" : "secondary"}>{u.isActive ? "Active" : "Inactive"}</Badge></TableCell>
                    </TableRow>
                  ))}
                </TableBody></Table>
              )}
            </CardContent></Card>
          </TabsContent>

          <TabsContent value="journeys">
            <Card><CardHeader><CardTitle>All Journeys</CardTitle></CardHeader><CardContent>
              {loading ? <p>Loading...</p> : (
                <Table><TableHeader><TableRow><TableHead>ID</TableHead><TableHead>User ID</TableHead><TableHead>Route</TableHead><TableHead>Fare</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
                <TableBody>
                  {journeys.map(j => (
                    <TableRow key={j.journey_id}>
                      <TableCell className="font-mono text-xs">{j.journey_id}</TableCell>
                      <TableCell className="font-mono">{j.user_id}</TableCell>
                      <TableCell>{j.boarding_stop} → {j.exit_stop || "..."}</TableCell>
                      <TableCell>₹{j.fare}</TableCell>
                      <TableCell><Badge variant={j.status === 'completed' ? "default" : "outline"}>{j.status}</Badge></TableCell>
                    </TableRow>
                  ))}
                </TableBody></Table>
              )}
            </CardContent></Card>
          </TabsContent>

          <TabsContent value="transactions">
            <Card><CardHeader><CardTitle>All Transactions</CardTitle></CardHeader><CardContent>
              {loading ? <p>Loading...</p> : (
                <Table><TableHeader><TableRow><TableHead>ID</TableHead><TableHead>User ID</TableHead><TableHead>Type</TableHead><TableHead>Amount</TableHead><TableHead>Date</TableHead></TableRow></TableHeader>
                <TableBody>
                  {transactions.map(t => (
                    <TableRow key={t.transaction_id}>
                      <TableCell className="font-mono text-xs">{t.transaction_id}</TableCell>
                      <TableCell className="font-mono">{t.user_id}</TableCell>
                      <TableCell><Badge variant={t.type === 'wallet_load' ? "default" : "secondary"}>{t.type}</Badge></TableCell>
                      <TableCell className={t.type === 'wallet_load' ? 'text-green-600' : 'text-red-600'}>{t.type === 'wallet_load' ? '+' : '-'}₹{t.amount}</TableCell>
                      <TableCell className="text-sm">{new Date(t.timestamp).toLocaleString()}</TableCell>
                    </TableRow>
                  ))}
                </TableBody></Table>
              )}
            </CardContent></Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};
export default Admin;