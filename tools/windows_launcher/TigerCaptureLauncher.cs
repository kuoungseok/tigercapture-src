using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Windows.Forms;

internal static class TigerCaptureLauncher
{
    [STAThread]
    private static int Main(string[] args)
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string frozenExe = Path.Combine(root, "dist", "TigerCapture", "TigerCapture.exe");
        string pythonw = Path.Combine(root, ".venv", "Scripts", "pythonw.exe");
        string python = Path.Combine(root, ".venv", "Scripts", "python.exe");
        string app = Path.Combine(root, "main.py");

        if (File.Exists(pythonw) && File.Exists(app))
        {
            return Start(root, pythonw, Quote(app) + AppendArgs(args));
        }

        if (File.Exists(python) && File.Exists(app))
        {
            return Start(root, python, Quote(app) + AppendArgs(args));
        }

        if (File.Exists(frozenExe))
        {
            return Start(root, frozenExe, QuoteArgs(args));
        }

        string message =
            "TigerCapture could not find a runnable app.\n\n" +
            "Expected one of:\n" +
            frozenExe + "\n" +
            pythonw + "\n" +
            python + "\n\n" +
            "Run build.ps1 or recreate .venv, then try again.";
        MessageBox.Show(message, "TigerCapture", MessageBoxButtons.OK, MessageBoxIcon.Error);
        return 1;
    }

    private static int Start(string workingDirectory, string fileName, string arguments)
    {
        try
        {
            ProcessStartInfo psi = new ProcessStartInfo
            {
                FileName = fileName,
                Arguments = arguments,
                WorkingDirectory = workingDirectory,
                UseShellExecute = false,
            };
            Process.Start(psi);
            return 0;
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "TigerCapture launch failed", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }

    private static string AppendArgs(string[] args)
    {
        string quoted = QuoteArgs(args);
        return string.IsNullOrWhiteSpace(quoted) ? "" : " " + quoted;
    }

    private static string QuoteArgs(string[] args)
    {
        if (args == null || args.Length == 0)
        {
            return "";
        }
        return string.Join(" ", args.Select(Quote));
    }

    private static string Quote(string value)
    {
        if (value == null)
        {
            return "\"\"";
        }
        return "\"" + value.Replace("\"", "\\\"") + "\"";
    }
}
