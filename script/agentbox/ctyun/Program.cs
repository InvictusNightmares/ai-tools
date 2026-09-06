using CtYun;
using CtYun.Models;
using System.Buffers.Binary;
using System.Net.Http;
using System.Net.WebSockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

const string DataDir = "/data";
const string ChallengeDir = "/challenges";
var command = args.FirstOrDefault() ?? "run";
if (args.Length > 1 || !new[] { "run", "login", "health", "self-test", "check-config", "help" }.Contains(command))
    return 64;
if (command == "help")
{
    Console.WriteLine("CtYun Agentbox: run | login (interactive human CAPTCHA/SMS) | health | check-config | self-test");
    return 0;
}
if (command == "self-test") return Policy.SelfTest();
if (command == "health")
{
    try
    {
        var health = JsonSerializer.Deserialize<Health>(File.ReadAllText($"{DataDir}/health.json"));
        return health?.State == "connected" && DateTimeOffset.UtcNow - health.Time < TimeSpan.FromSeconds(150) ? 0 : 1;
    }
    catch { return 1; }
}
try
{
    var config = JsonSerializer.Deserialize<Config>(File.ReadAllText($"{DataDir}/accounts.json"));
    Policy.Validate(config);
    if (command == "check-config") { Console.WriteLine("CONFIG_OK"); return 0; }
    // login and the daemon share an exclusive lock: renewal must stop the worker first.
    using var processLock = new FileStream($"{DataDir}/worker.lock", FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
    using var cts = new CancellationTokenSource();
    Console.CancelKeyPress += (_, e) => { e.Cancel = true; cts.Cancel(); };
    var devicePath = $"{DataDir}/device-code";
    if (!File.Exists(devicePath)) SavePrivate(devicePath, "web_" + Convert.ToHexString(RandomNumberGenerator.GetBytes(16)).ToLowerInvariant());
    var device = File.ReadAllText(devicePath).Trim();
    if (!System.Text.RegularExpressions.Regex.IsMatch(device, "^web_[a-zA-Z0-9]{32}$")) throw new InvalidDataException();
    using var api = new CtYunApi(device, HumanCaptcha);
    var sessionPath = $"{DataDir}/session.json";
    if (command == "login")
    {
        if (Console.IsInputRedirected) { Console.WriteLine("LOGIN_REQUIRES_HUMAN_TERMINAL"); return 78; }
        if (!await api.LoginAsync(config.User, config.Password)) return 1;
        if (!api.LoginInfo.BondedDevice)
        {
            Console.WriteLine("DEVICE_BINDING_REQUIRED: an SMS will be requested for this account.");
            if (!await api.GetSmsCodeAsync(config.User)) return 1;
            Console.Write("Enter the SMS code: ");
            var code = ReadHidden().Trim();
            if (!System.Text.RegularExpressions.Regex.IsMatch(code, "^[0-9]{4,8}$") || !await api.BindingDeviceAsync(code)) return 1;
            api.LoginInfo.BondedDevice = true;
        }
        var desktops = await api.GetLlientListAsync();
        Policy.Target(desktops, config.DesktopId);
        SavePrivate(sessionPath, JsonSerializer.Serialize(new SavedSession(Subject(config.User, device), api.LoginInfo)));
        Console.WriteLine("LOGIN_OK: private session saved; only the configured desktop can be connected.");
        return 0;
    }
    if (!File.Exists(sessionPath))
    {
        SetHealth("login-required"); Console.WriteLine("LOGIN_REQUIRED: run the interactive login command.");
        await Task.Delay(Timeout.InfiniteTimeSpan, cts.Token); return 78;
    }
    var saved = JsonSerializer.Deserialize<SavedSession>(File.ReadAllText(sessionPath));
    if (saved?.Subject != Subject(config.User, device)) throw new InvalidDataException();
    api.LoginInfo = saved.Login;
    if (api.LoginInfo?.UserId <= 0 || string.IsNullOrWhiteSpace(api.LoginInfo?.SecretKey)) throw new InvalidDataException();
    while (!cts.IsCancellationRequested)
    {
        try
        {
            var desktop = Policy.Target(await api.GetLlientListAsync(), config.DesktopId);
            if (desktop.UseStatusText != "运行中") throw new InvalidOperationException("TARGET_NOT_RUNNING");
            var result = await api.ConnectAsync(config.DesktopId);
            if (!result.Success || result.Data?.DesktopInfo == null) throw new InvalidOperationException("CONNECT_REJECTED");
            if (result.Data.DesktopInfo.DesktopId.ToString() != config.DesktopId) throw new InvalidDataException();
            await KeepAlive(api, result.Data.DesktopInfo, config, cts.Token);
        }
        catch (OperationCanceledException) when (cts.IsCancellationRequested) { break; }
        catch (Exception ex)
        {
            SetHealth("retrying");
            // Exception messages and platform responses may contain tokens or URLs.
            Console.WriteLine($"KEEPALIVE_RETRY error={ex.GetType().Name}; verify network or renew login if persistent.");
            await Task.Delay(TimeSpan.FromSeconds(60), cts.Token);
        }
    }
    return 0;
}
catch (OperationCanceledException) { return 0; }
catch (Exception ex) { Console.WriteLine($"START_FAILED error={ex.GetType().Name}"); return 1; }

async Task<string> HumanCaptcha(byte[] image)
{
    if (Console.IsInputRedirected) throw new InvalidOperationException("HUMAN_LOGIN_REQUIRED");
    if (image == null || image.Length == 0 || image.Length > 1024 * 1024) throw new InvalidDataException();
    var path = $"{ChallengeDir}/captcha.png";
    try
    {
        await File.WriteAllBytesAsync(path, image);
        File.SetUnixFileMode(path, UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.GroupRead);
        Console.WriteLine("HUMAN_CAPTCHA_REQUIRED: open the private /challenges/captcha.png file yourself.");
        Console.Write("Enter the CAPTCHA shown in that image: ");
        return ReadHidden().Trim();
    }
    finally { File.Delete(path); }
}

string ReadHidden()
{
    var value = new StringBuilder();
    while (true)
    {
        var key = Console.ReadKey(intercept: true);
        if (key.Key == ConsoleKey.Enter) { Console.WriteLine(); return value.ToString(); }
        if (key.Key == ConsoleKey.Backspace && value.Length > 0) value.Length--;
        else if (!char.IsControl(key.KeyChar) && value.Length < 64) value.Append(key.KeyChar);
    }
}

void SavePrivate(string path, string value)
{
    var temp = path + "." + Guid.NewGuid().ToString("N") + ".new";
    try
    {
    using (var file = new FileStream(temp, new FileStreamOptions { Mode = FileMode.CreateNew, Access = FileAccess.Write, UnixCreateMode = UnixFileMode.UserRead | UnixFileMode.UserWrite }))
    using (var writer = new StreamWriter(file)) writer.Write(value);
    File.Move(temp, path, true);
    }
    finally { File.Delete(temp); }
}

string Subject(string user, string device) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(user.Trim() + "\n" + device)));

void SetHealth(string state)
{
    // Atomic replacement lets the healthcheck read a complete, non-secret record.
    var path = $"{DataDir}/health.json";
    var temp = path + ".tmp";
    File.WriteAllText(temp, JsonSerializer.Serialize(new Health(state, DateTimeOffset.UtcNow)));
    File.Move(temp, path, true);
}

async Task KeepAlive(CtYunApi api, DesktopInfo info, Config config, CancellationToken stop)
{
    var uri = Policy.Endpoint(info.ClinkLvsOutHost, config.DesktopId);
    using var cycle = CancellationTokenSource.CreateLinkedTokenSource(stop);
    cycle.CancelAfter(TimeSpan.FromSeconds(config.KeepAliveSeconds));
    using var ws = new ClientWebSocket();
    using var handler = Policy.WebSocketHandler();
    using var invoker = new HttpMessageInvoker(handler);
    ws.Options.SetRequestHeader("Origin", "https://pc.ctyun.cn");
    ws.Options.AddSubProtocol("binary");
    bool ready = false;
    try
    {
        await ws.ConnectAsync(uri, invoker, cycle.Token);
        var connect = new ConnecMessage { type = 1, ssl = 1, host = uri.Host, port = uri.Port.ToString(), ca = info.CaCert, cert = info.ClientCert, key = info.ClientKey, servername = info.Host + ":" + info.Port, oqs = 0 };
        await ws.SendAsync(JsonSerializer.SerializeToUtf8Bytes(connect), WebSocketMessageType.Text, true, cycle.Token);
        await Task.Delay(500, cycle.Token);
        await ws.SendAsync(Convert.FromBase64String("UkVEUQIAAAACAAAAGgAAAAAAAAABAAEAAAABAAAAEgAAAAkAAAAECAAA"), WebSocketMessageType.Binary, true, cycle.Token);
        var buffer = new byte[8192];
        while (ws.State == WebSocketState.Open)
        {
            using var message = new MemoryStream();
            WebSocketReceiveResult received;
            do
            {
                received = await ws.ReceiveAsync(new ArraySegment<byte>(buffer), cycle.Token);
                if (received.MessageType == WebSocketMessageType.Close) throw new IOException();
                if (message.Length + received.Count > 1024 * 1024) throw new InvalidDataException();
                message.Write(buffer, 0, received.Count);
            } while (!received.EndOfMessage);
            var bytes = message.ToArray();
            if (bytes.Length == 0) continue;
            if (bytes.AsSpan().StartsWith("REDQ"u8))
            {
                if (bytes.Length < 182) throw new InvalidDataException();
                await ws.SendAsync(new Encryption().Execute(bytes), WebSocketMessageType.Binary, true, cycle.Token);
                continue;
            }
            foreach (var type in Policy.FrameTypes(bytes))
            {
                if (type != 103) continue;
                var payload = JsonSerializer.SerializeToUtf8Bytes(new { type = 1, userName = api.LoginInfo.UserName, userInfo = "", userId = api.LoginInfo.UserId });
                await ws.SendAsync(new SendInfo { Type = 118, Data = payload }.ToBuffer(true), WebSocketMessageType.Binary, true, cycle.Token);
                ready = true;
                SetHealth("connected");
                Console.WriteLine("KEEPALIVE_HANDSHAKE_OK target=" + config.DesktopId);
            }
        }
    }
    catch (OperationCanceledException) when (!stop.IsCancellationRequested && ready) { /* expected cycle renewal */ }
    finally { ws.Abort(); }
    if (!ready) throw new IOException();
}

record SavedSession(string Subject, LoginInfo Login);
record Health(string State, DateTimeOffset Time);
sealed class Config
{
    public string User { get; set; }
    public string Password { get; set; }
    public string DesktopId { get; set; }
    public int KeepAliveSeconds { get; set; } = 60;
}
static class Policy
{
    public static SocketsHttpHandler WebSocketHandler() => new() { AllowAutoRedirect = false, Proxy = HttpClient.DefaultProxy, ConnectTimeout = TimeSpan.FromSeconds(20) };

    public static void Validate(Config c)
    {
        if (c == null || string.IsNullOrWhiteSpace(c.User) || string.IsNullOrWhiteSpace(c.Password) ||
            !System.Text.RegularExpressions.Regex.IsMatch(c.DesktopId ?? "", "^[0-9]{1,20}$") || c.KeepAliveSeconds != 60)
            throw new InvalidDataException();
    }
    public static Desktop Target(List<Desktop> desktops, string id)
    {
        var matches = desktops?.Where(d => d.DesktopId == id).ToArray();
        if (matches?.Length != 1) throw new InvalidDataException();
        return matches[0];
    }
    public static Uri Endpoint(string host, string id)
    {
        if (!Uri.TryCreate("wss://" + host, UriKind.Absolute, out var root) || root.AbsolutePath != "/" || root.UserInfo != "" || root.Query != "" || root.Fragment != "" || root.IsLoopback)
            throw new InvalidDataException();
        return new Uri(root, "/clinkProxy/" + id + "/MAIN");
    }
    public static List<ushort> FrameTypes(byte[] bytes)
    {
        var types = new List<ushort>();
        // The SPICE auth result is a standalone uint32; it is not an app frame.
        if (bytes.Length == 4)
        {
            if (BinaryPrimitives.ReadUInt32LittleEndian(bytes) != 0) throw new InvalidDataException();
            return types;
        }
        int offset = 0;
        while (offset < bytes.Length)
        {
            if (bytes.Length - offset < 6)
            {
                if (bytes.Skip(offset).All(value => value == 0)) break;
                throw new InvalidDataException();
            }
            int length = BinaryPrimitives.ReadInt32LittleEndian(bytes.AsSpan(offset + 2, 4));
            if (length < 0 || length > bytes.Length - offset - 6) throw new InvalidDataException();
            types.Add(BinaryPrimitives.ReadUInt16LittleEndian(bytes.AsSpan(offset, 2)));
            offset += 6 + length;
        }
        return types;
    }
    static async Task NoRedirect()
    {
        using var first = new System.Net.Sockets.TcpListener(System.Net.IPAddress.Loopback, 0);
        using var other = new System.Net.Sockets.TcpListener(System.Net.IPAddress.Loopback, 0);
        first.Start(); other.Start();
        int firstPort = ((System.Net.IPEndPoint)first.LocalEndpoint).Port;
        int otherPort = ((System.Net.IPEndPoint)other.LocalEndpoint).Port;
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(4));
        var server = Task.Run(async () =>
        {
            using var client = await first.AcceptTcpClientAsync(timeout.Token);
            using var stream = client.GetStream();
            var request = new byte[4096];
            await stream.ReadAsync(request, timeout.Token);
            var response = Encoding.ASCII.GetBytes($"HTTP/1.1 302 Found\r\nLocation: http://127.0.0.1:{otherPort}/other\r\nContent-Length: 0\r\nConnection: close\r\n\r\n");
            await stream.WriteAsync(response, timeout.Token);
        });
        using var handler = WebSocketHandler();
        handler.UseProxy = false; // local test fixture only
        using var invoker = new HttpMessageInvoker(handler);
        using var ws = new ClientWebSocket();
        try { await ws.ConnectAsync(new Uri($"ws://127.0.0.1:{firstPort}/"), invoker, timeout.Token); }
        catch (WebSocketException) { }
        catch (OperationCanceledException) { }
        await server;
        if (other.Pending()) throw new Exception("WebSocket followed a cross-origin redirect");
    }
    public static int SelfTest()
    {
        int passed = 0;
        void Good(bool value) { if (!value) throw new Exception("test failed"); passed++; }
        void Reject(Action action) { try { action(); } catch (InvalidDataException) { passed++; return; } throw new Exception("expected rejection"); }
        var target = new Desktop { DesktopId = "2" };
        Good(ReferenceEquals(Target(new() { new() { DesktopId = "1" }, target }, "2"), target));
        Reject(() => Target(new() { target }, "1"));
        Reject(() => Target(new() { target, target }, "2"));
        Reject(() => Validate(new() { User = "test", Password = "test", DesktopId = "2/../3" }));
        Reject(() => Endpoint("localhost:443", "2"));
        Reject(() => Endpoint("example.com/other", "2"));
        Good(Endpoint("example.com:8443", "2").AbsolutePath == "/clinkProxy/2/MAIN");
        Good(FrameTypes(new byte[] {103, 0, 0, 0, 0, 0}).Single() == 103);
        Good(FrameTypes(new byte[] {103, 0, 0, 0, 0, 0, 0, 0, 0, 0}).Single() == 103);
        Reject(() => FrameTypes(new byte[] {103, 0, 0, 0, 0, 0, 1}));
        Reject(() => FrameTypes(new byte[] {1, 0, 0, 0}));
        Reject(() => FrameTypes(new byte[] {103, 0, 9, 0, 0, 0}));
        Reject(() => FrameTypes(new byte[] {103, 0, 255, 255, 255, 255}));
        NoRedirect().GetAwaiter().GetResult(); passed++;
        Console.WriteLine($"SELF_TEST_OK {passed} checks");
        return 0;
    }
}
