"""Own the complete candidate process tree until an update is confirmed."""
from __future__ import annotations

import ctypes
import subprocess
import time
from ctypes import wintypes


class UnconfirmedTerminationError(RuntimeError):
    """A failed launch may still own a process, despite cleanup attempts."""


class _StartupInfo(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(wintypes.BYTE)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _ProcessInfo(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class _BasicLimits(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
    )]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimits),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _Accounting(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", ctypes.c_int64),
        ("TotalKernelTime", ctypes.c_int64),
        ("ThisPeriodTotalUserTime", ctypes.c_int64),
        ("ThisPeriodTotalKernelTime", ctypes.c_int64),
        ("TotalPageFaultCount", wintypes.DWORD),
        ("TotalProcesses", wintypes.DWORD),
        ("ActiveProcesses", wintypes.DWORD),
        ("TotalTerminatedProcesses", wintypes.DWORD),
    ]


class _WindowsAPI:
    def __init__(self):
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ((wintypes.LPVOID, wintypes.LPCWSTR), wintypes.HANDLE),
            "SetInformationJobObject": ((wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD), wintypes.BOOL),
            "QueryInformationJobObject": ((wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD, wintypes.LPVOID), wintypes.BOOL),
            "CreateProcessW": ((wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.LPVOID, wintypes.LPVOID, wintypes.BOOL, wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR, ctypes.POINTER(_StartupInfo), ctypes.POINTER(_ProcessInfo)), wintypes.BOOL),
            "AssignProcessToJobObject": ((wintypes.HANDLE, wintypes.HANDLE), wintypes.BOOL),
            "ResumeThread": ((wintypes.HANDLE,), wintypes.DWORD),
            "GetExitCodeProcess": ((wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)), wintypes.BOOL),
            "TerminateJobObject": ((wintypes.HANDLE, wintypes.UINT), wintypes.BOOL),
            "TerminateProcess": ((wintypes.HANDLE, wintypes.UINT), wintypes.BOOL),
            "WaitForSingleObject": ((wintypes.HANDLE, wintypes.DWORD), wintypes.DWORD),
            "CloseHandle": ((wintypes.HANDLE,), wintypes.BOOL),
        }
        for name, (argtypes, restype) in signatures.items():
            function = getattr(self.kernel, name)
            function.argtypes = argtypes
            function.restype = restype

    @staticmethod
    def _check(result):
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())
        return result

    def create_job(self):
        return self._check(self.kernel.CreateJobObjectW(None, None))

    def kill_on_close(self, job, enabled):
        limits = _ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000 if enabled else 0
        self._check(self.kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)))

    def create_suspended(self, command, cwd):
        startup = _StartupInfo()
        startup.cb = ctypes.sizeof(startup)
        info = _ProcessInfo()
        self._check(self.kernel.CreateProcessW(
            command[0], ctypes.create_unicode_buffer(subprocess.list2cmdline(command)),
            None, None, False, 0x00000004, None, cwd,
            ctypes.byref(startup), ctypes.byref(info),
        ))
        return info.hProcess, info.hThread, info.dwProcessId

    def assign(self, job, process):
        self._check(self.kernel.AssignProcessToJobObject(job, process))

    def resume(self, thread):
        if self.kernel.ResumeThread(thread) == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())

    def poll(self, process):
        code = wintypes.DWORD()
        self._check(self.kernel.GetExitCodeProcess(process, ctypes.byref(code)))
        return None if code.value == 259 else code.value

    def terminate_job(self, job):
        self._check(self.kernel.TerminateJobObject(job, 1))

    def terminate_process(self, process):
        self._check(self.kernel.TerminateProcess(process, 1))

    def wait(self, process, timeout):
        result = self.kernel.WaitForSingleObject(process, max(0, int(timeout * 1000)))
        if result == 0x00000102:
            raise TimeoutError("candidate process did not exit")
        if result != 0:
            raise OSError(f"candidate wait failed: 0x{result:08x}")

    def active_processes(self, job):
        accounting = _Accounting()
        self._check(self.kernel.QueryInformationJobObject(job, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None))
        return accounting.ActiveProcesses

    def close(self, handle):
        self._check(self.kernel.CloseHandle(handle))


class JobProcess:
    """Launch suspended, then own every descendant even after its parent exits."""

    def __init__(self, command, *, cwd, api=None):
        self._api = _WindowsAPI() if api is None else api
        self._job = self._process = self._thread = None
        self._assigned = False
        try:
            self._job = self._api.create_job()
            self._api.kill_on_close(self._job, True)
            self._process, self._thread, self.pid = self._api.create_suspended(command, cwd)
            self._api.assign(self._job, self._process)
            self._assigned = True
            self._api.resume(self._thread)
            self._api.close(self._thread)
            self._thread = None
        except BaseException as launch_error:
            stopped = self.stop_tree()
            self.close()
            if not stopped:
                raise UnconfirmedTerminationError(
                    "candidate launch failed and process termination is unconfirmed"
                ) from launch_error
            raise

    def poll(self):
        return self._api.poll(self._process)

    def stop_tree(self, *, timeout=8.0):
        """Wait for the whole job, never just the outer bootloader process."""
        try:
            if self._assigned:
                self._api.terminate_job(self._job)
                deadline = time.monotonic() + max(0.0, timeout)
                while self._api.active_processes(self._job):
                    if time.monotonic() >= deadline:
                        return False
                    time.sleep(0.05)
            elif self._process is not None:
                # Assignment failed while the only thread was still suspended.
                self._api.terminate_process(self._process)
                self._api.wait(self._process, max(0.0, timeout))
            return True
        except OSError:
            return False

    def release(self):
        """A healthy application must survive the helper closing its handles."""
        if self._job is not None:
            self._api.kill_on_close(self._job, False)
        self.close()

    def close(self):
        # The job is non-inheritable and stays armed until release(). Closing it
        # also contains a helper exception/exit while a candidate is unconfirmed.
        for field in ("_thread", "_process", "_job"):
            handle = getattr(self, field)
            if handle is not None:
                try:
                    self._api.close(handle)
                except OSError:
                    # Keep ownership so the helper's final cleanup can retry.
                    continue
                setattr(self, field, None)
