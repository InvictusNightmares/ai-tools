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
        // The proxy returns a one-byte acknowledgement before the SPICE stream.
        // WebSocket messages can split or combine any subsequent protocol records.
        var input = new SpiceStream(ws);
        Policy.ProxyReply(await input.ReadExactly(1, cycle.Token));
        await ws.SendAsync(Convert.FromBase64String("UkVEUQIAAAACAAAAGgAAAAAAAAABAAEAAAABAAAAEgAAAAkAAAAECAAA"), WebSocketMessageType.Binary, true, cycle.Token);
        var linkHeader = await input.ReadExactly(16, cycle.Token);
        var linkBody = await input.ReadExactly(Policy.LinkBodyLength(linkHeader), cycle.Token);
        Policy.LinkReply(linkBody);
        await ws.SendAsync(new Encryption().Execute(linkHeader.Concat(linkBody).ToArray()), WebSocketMessageType.Binary, true, cycle.Token);
        Policy.AuthReply(await input.ReadExactly(4, cycle.Token));
        while (ws.State == WebSocketState.Open)
        {
            var header = await input.ReadExactly(6, cycle.Token);
            var body = await input.ReadExactly(Policy.FrameBodyLength(header), cycle.Token);
            if (BinaryPrimitives.ReadUInt16LittleEndian(header) != 103) continue;
            // MAIN_INIT contains eight uint32 fields. A header alone is not a handshake.
            if (body.Length < 32) throw new InvalidDataException();
            var payload = JsonSerializer.SerializeToUtf8Bytes(new { type = 1, userName = api.LoginInfo.UserName, userInfo = "", userId = api.LoginInfo.UserId });
            await ws.SendAsync(new SendInfo { Type = 118, Data = payload }.ToBuffer(true), WebSocketMessageType.Binary, true, cycle.Token);
            if (!ready)
            {
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
    public static void ProxyReply(byte[] reply)
    {
        if (reply.Length != 1 || reply[0] != 1) throw new InvalidDataException();
    }
    public static int LinkBodyLength(byte[] header)
    {
        if (header.Length != 16 || !header.AsSpan(0, 4).SequenceEqual("REDQ"u8) ||
            BinaryPrimitives.ReadUInt32LittleEndian(header.AsSpan(4)) != 2) throw new InvalidDataException();
        uint length = BinaryPrimitives.ReadUInt32LittleEndian(header.AsSpan(12));
        if (length < 178 || length > SpiceStream.MaxRecordBytes - 16) throw new InvalidDataException();
        return (int)length;
    }
    public static void LinkReply(byte[] body)
    {
        if (body.Length < 178 || BinaryPrimitives.ReadUInt32LittleEndian(body) != 0) throw new InvalidDataException();
        uint common = BinaryPrimitives.ReadUInt32LittleEndian(body.AsSpan(166));
        uint channel = BinaryPrimitives.ReadUInt32LittleEndian(body.AsSpan(170));
        uint offset = BinaryPrimitives.ReadUInt32LittleEndian(body.AsSpan(174));
        if (common == 0 || offset < 178 || (ulong)offset + ((ulong)common + channel) * 4 > (ulong)body.Length)
            throw new InvalidDataException();
        // Our request advertises the mini header capability; require server support.
        if ((BinaryPrimitives.ReadUInt32LittleEndian(body.AsSpan((int)offset)) & (1u << 3)) == 0)
            throw new InvalidDataException();
    }
    public static void AuthReply(byte[] reply)
    {
        if (reply.Length != 4 || BinaryPrimitives.ReadUInt32LittleEndian(reply) != 0) throw new InvalidDataException();
    }
    public static int FrameBodyLength(byte[] header)
    {
        if (header.Length != 6) throw new InvalidDataException();
        uint length = BinaryPrimitives.ReadUInt32LittleEndian(header.AsSpan(2));
        if (length > SpiceStream.MaxRecordBytes) throw new InvalidDataException();
        return (int)length;
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
    static async Task WireRegression(byte[] wire, int chunk)
    {
        using var socket = new FixtureSocket(wire, chunk);
        var input = new SpiceStream(socket);
        ProxyReply(await input.ReadExactly(1, CancellationToken.None));
        var header = await input.ReadExactly(16, CancellationToken.None);
        LinkReply(await input.ReadExactly(LinkBodyLength(header), CancellationToken.None));
        AuthReply(await input.ReadExactly(4, CancellationToken.None));
        var frame = await input.ReadExactly(6, CancellationToken.None);
        var data = await input.ReadExactly(FrameBodyLength(frame), CancellationToken.None);
        if (BinaryPrimitives.ReadUInt16LittleEndian(frame) != 103 || data.Length != 32)
            throw new Exception("split/coalesced protocol regression");
    }
    static async Task RejectAsyncRead()
    {
        foreach (var messageType in new[] {WebSocketMessageType.Text, WebSocketMessageType.Close})
        {
            using var socket = new FixtureSocket(new byte[] {1}, 1, messageType);
            try { await new SpiceStream(socket).ReadExactly(1, CancellationToken.None); }
            catch (Exception ex) when (ex is IOException or InvalidDataException) { continue; }
            throw new Exception("nonbinary protocol input accepted");
        }
        using var truncated = new FixtureSocket(new byte[] {103}, 1);
        try { await new SpiceStream(truncated).ReadExactly(6, CancellationToken.None); }
        catch (IOException) { return; }
        throw new Exception("truncated protocol input accepted");
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
        ProxyReply(new byte[] {1}); passed++;
        Reject(() => ProxyReply(new byte[] {0}));
        Reject(() => ProxyReply(new byte[] {1, 1}));
        AuthReply(new byte[4]); passed++;
        Reject(() => AuthReply(new byte[] {1, 0, 0, 0}));
        Good(FrameBodyLength(new byte[] {103, 0, 32, 0, 0, 0}) == 32);
        Reject(() => FrameBodyLength(new byte[] {103}));
        Reject(() => FrameBodyLength(new byte[] {103, 0, 255, 255, 255, 255}));
        byte[] link = new byte[16];
        "REDQ"u8.CopyTo(link); link[4] = 2; link[12] = 182;
        Good(LinkBodyLength(link) == 182);
        Reject(() => LinkBodyLength(new byte[16]));
        byte[] body = new byte[182];
        body[166] = 1; body[174] = 178; body[178] = 8;
        LinkReply(body); passed++;
        body[178] = 0; Reject(() => LinkReply(body)); body[178] = 8;
        body[0] = 1; Reject(() => LinkReply(body)); body[0] = 0;
        var wire = new byte[] {1}.Concat(link).Concat(body).Concat(new byte[4])
            .Concat(new byte[] {103, 0, 32, 0, 0, 0}).Concat(new byte[32]).ToArray();
        foreach (int chunk in new[] {1, 3, 16, wire.Length})
        {
            WireRegression(wire, chunk).GetAwaiter().GetResult(); passed++;
        }
        RejectAsyncRead().GetAwaiter().GetResult(); passed++;
        NoRedirect().GetAwaiter().GetResult(); passed++;
        Console.WriteLine($"SELF_TEST_OK {passed} checks");
        return 0;
    }
}

// This bridge carries a byte stream, independent of WebSocket message boundaries.
sealed class SpiceStream(WebSocket socket)
{
    public const int MaxRecordBytes = 1024 * 1024;
    readonly byte[] buffer = new byte[8192];
    int offset, available;
    public async Task<byte[]> ReadExactly(int length, CancellationToken stop)
    {
        if (length < 0 || length > MaxRecordBytes) throw new InvalidDataException();
        var result = new byte[length];
        int written = 0;
        while (written < length)
        {
            if (available == 0)
            {
                var received = await socket.ReceiveAsync(new ArraySegment<byte>(buffer), stop);
                if (received.MessageType == WebSocketMessageType.Close) throw new EndOfStreamException();
                if (received.MessageType != WebSocketMessageType.Binary) throw new InvalidDataException();
                offset = 0; available = received.Count;
                if (available == 0) continue;
            }
            int count = Math.Min(available, length - written);
            buffer.AsSpan(offset, count).CopyTo(result.AsSpan(written));
            offset += count; available -= count; written += count;
        }
        return result;
    }
}

sealed class FixtureSocket(byte[] bytes, int chunk, WebSocketMessageType messageType = WebSocketMessageType.Binary) : WebSocket
{
    int offset;
    public override WebSocketCloseStatus? CloseStatus => null;
    public override string CloseStatusDescription => null;
    public override WebSocketState State => WebSocketState.Open;
    public override string SubProtocol => "binary";
    public override void Abort() { }
    public override void Dispose() { }
    public override Task CloseAsync(WebSocketCloseStatus status, string description, CancellationToken stop) => Task.CompletedTask;
    public override Task CloseOutputAsync(WebSocketCloseStatus status, string description, CancellationToken stop) => Task.CompletedTask;
    public override Task SendAsync(ArraySegment<byte> buffer, WebSocketMessageType type, bool endOfMessage, CancellationToken stop) => Task.CompletedTask;
    public override Task<WebSocketReceiveResult> ReceiveAsync(ArraySegment<byte> buffer, CancellationToken stop)
    {
        stop.ThrowIfCancellationRequested();
        if (offset == bytes.Length) return Task.FromResult(new WebSocketReceiveResult(0, WebSocketMessageType.Close, true));
        int count = Math.Min(Math.Min(chunk, buffer.Count), bytes.Length - offset);
        Array.Copy(bytes, offset, buffer.Array, buffer.Offset, count); offset += count;
        return Task.FromResult(new WebSocketReceiveResult(count, messageType, true));
    }
}
