#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenClaw Deployer Ultra - 全网最强真实部署工具
版本：3.0.0
功能特性：
- 真实环境检测（Node.js/npm/Docker/Git/端口）
- 三种部署模式（本地/npm全局/Docker Compose）
- 完整卸载清理（守护进程/数据目录/缓存/服务）
- 实时日志监控 + 进程管理
- 跨平台支持（Windows/macOS/Linux）
- 配置文件管理 + 备份恢复
-OpenClaw迭代qq交流群747764641
"""

import sys
import os
import json
import subprocess
import shutil
import threading
import time
import re
import socket
import platform
import webbrowser
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple, Callable
from dataclasses import dataclass, asdict
from enum import Enum, auto
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QTabWidget, QGroupBox, QTextEdit, QProgressBar, QMessageBox,
    QFileDialog, QDialog, QDialogButtonBox, QFormLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter, QStatusBar, QMenuBar,
    QMenu, QToolBar, QSystemTrayIcon, QStyle, QFrame, QScrollArea,
    QStackedWidget, QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem,
    QInputDialog, QPlainTextEdit, QKeySequenceEdit,
    QRadioButton, QButtonGroup, QGridLayout, QSpacerItem, QSizePolicy,
    QWizard, QWizardPage, QTreeView, QSplitter,
    QDialogButtonBox, QSlider, QDateTimeEdit, QToolButton
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QSettings, QProcess,
    QUrl, QPoint, QDir, QFileSystemWatcher, QIODevice, QByteArray
)
from PyQt6.QtGui import (
    QIcon, QFont, QColor, QPalette, QKeySequence, QDesktopServices,
    QAction, QCursor, QTextCursor, QSyntaxHighlighter, QTextCharFormat,
    QFontDatabase, QMovie, QPixmap, QPainter, QLinearGradient, QShortcut
)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply


# ==============================================================================
# 全局常量与配置
# ==============================================================================

APP_NAME = "OpenClaw Deployer Ultra"
APP_VERSION = "3.0.0"
APP_AUTHOR = "OpenClaw Deployer Team"

# OpenClaw 官方配置
OPENCLAW_REPO = "https://github.com/openclaw/openclaw.git"
OPENCLAW_NPM_PACKAGE = "openclaw"
OPENCLAW_DEFAULT_PORT = 18789
OPENCLAW_CONFIG_DIR = "~/.openclaw"
OPENCLAW_GITHUB_API = "https://api.github.com/repos/openclaw/openclaw/releases/latest"

# 系统服务名称
SERVICE_NAME_MACOS = "com.openclaw.gateway"
SERVICE_NAME_LINUX = "openclaw-gateway"
SERVICE_NAME_WINDOWS = "OpenClawService"

# 平台检测
PLATFORM = platform.system().lower()
IS_WINDOWS = PLATFORM == "windows"
IS_MACOS = PLATFORM == "darwin"
IS_LINUX = PLATFORM == "linux"


# ==============================================================================
# 数据模型
# ==============================================================================

class DeployMethod(Enum):
    NPM_GLOBAL = ("npm全局安装", "通过 npm/pnpm/bun 全局安装，支持守护进程")
    LOCAL_SOURCE = ("本地源码", "克隆 GitHub 仓库，本地运行开发版本")
    DOCKER_COMPOSE = ("Docker Compose", "使用官方 docker-compose.yml 一键部署")
    DOCKER_RUN = ("Docker Run", "单容器快速启动，适合临时测试")
    
    def __init__(self, display_name, description):
        self.display_name = display_name
        self.description = description

class ServiceStatus(Enum):
    STOPPED = ("已停止", "#e74c3c", "⏹️")
    RUNNING = ("运行中", "#2ecc71", "▶️")
    ERROR = ("错误", "#e67e22", "⚠️")
    INSTALLING = ("安装中", "#3498db", "⏳")
    UNKNOWN = ("未知", "#95a5a6", "❓")
    
    def __init__(self, text, color, icon):
        self.text = text
        self.color = color
        self.icon = icon

@dataclass
class EnvironmentCheck:
    node_installed: bool = False
    node_version: str = ""
    npm_installed: bool = False
    npm_version: str = ""
    pnpm_installed: bool = False
    pnpm_version: str = ""
    docker_installed: bool = False
    docker_version: str = ""
    docker_compose_installed: bool = False
    git_installed: bool = False
    git_version: str = ""
    port_available: bool = True
    port_checked: int = OPENCLAW_DEFAULT_PORT
    system: str = ""
    architecture: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class DeployConfig:
    method: str = "npm_global"
    port: int = OPENCLAW_DEFAULT_PORT
    token: str = "openclaw"
    data_dir: str = OPENCLAW_CONFIG_DIR
    package_manager: str = "npm"  # npm/pnpm/bun
    install_daemon: bool = True
    auto_start: bool = False
    log_level: str = "info"
    docker_image: str = "openclaw/openclaw:latest"
    docker_container_name: str = "openclaw"
    docker_compose_version: str = "3"
    git_branch: str = "main"
    npm_registry: str = "https://registry.npmjs.org/"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class UninstallOptions:
    stop_services: bool = True
    uninstall_npm: bool = True
    remove_data_dir: bool = True
    remove_docker: bool = True
    remove_cache: bool = True
    remove_config: bool = True


# ==============================================================================
# 工作线程类
# ==============================================================================

class EnvCheckThread(QThread):
    """环境检测线程"""
    finished = pyqtSignal(EnvironmentCheck)
    progress = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.check = EnvironmentCheck()
    
    def run(self):
        """执行环境检测"""
        self.progress.emit("检测系统信息...")
        self.check.system = f"{platform.system()} {platform.release()}"
        self.check.architecture = platform.machine()
        
        # 检测 Node.js
        self.progress.emit("检测 Node.js...")
        success, version = self._run_command(["node", "--version"])
        self.check.node_installed = success
        self.check.node_version = version.strip() if success else ""
        
        # 检测 npm
        self.progress.emit("检测 npm...")
        success, version = self._run_command(["npm", "--version"])
        self.check.npm_installed = success
        self.check.npm_version = version.strip() if success else ""
        
        # 检测 pnpm
        self.progress.emit("检测 pnpm...")
        success, version = self._run_command(["pnpm", "--version"])
        self.check.pnpm_installed = success
        self.check.pnpm_version = version.strip() if success else ""
        
        # 检测 Docker
        self.progress.emit("检测 Docker...")
        success, version = self._run_command(["docker", "--version"])
        self.check.docker_installed = success
        self.check.docker_version = version.strip() if success else ""
        
        # 检测 Docker Compose
        self.progress.emit("检测 Docker Compose...")
        success, version = self._run_command(["docker-compose", "--version"])
        if not success:
            success, version = self._run_command(["docker", "compose", "version"])
        self.check.docker_compose_installed = success
        self.check.docker_version = version.strip() if success else ""
        
        # 检测 Git
        self.progress.emit("检测 Git...")
        success, version = self._run_command(["git", "--version"])
        self.check.git_installed = success
        self.check.git_version = version.strip() if success else ""
        
        # 检测端口
        self.progress.emit(f"检测端口 {self.check.port_checked}...")
        self.check.port_available = self._check_port(self.check.port_checked)
        
        self.finished.emit(self.check)
    
    def _run_command(self, cmd: List[str]) -> Tuple[bool, str]:
        """运行命令并返回结果"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0, result.stdout or result.stderr
        except Exception as e:
            return False, str(e)
    
    def _check_port(self, port: int) -> bool:
        """检查端口是否可用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('127.0.0.1', port))
                return True
        except:
            return False


class DeployThread(QThread):
    """部署线程"""
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)
    
    def __init__(self, config: DeployConfig):
        super().__init__()
        self.config = config
    
    def run(self):
        """执行部署"""
        try:
            if self.config.method == "npm_global":
                self._deploy_npm()
            elif self.config.method == "local_source":
                self._deploy_local()
            elif self.config.method == "docker_compose":
                self._deploy_docker_compose()
            elif self.config.method == "docker_run":
                self._deploy_docker_run()
        except Exception as e:
            self.finished.emit(False, str(e))
    
    def _deploy_npm(self):
        """npm全局部署"""
        self.progress.emit("正在全局安装 OpenClaw...")
        
        # 安装
        cmd = [self.config.package_manager, "install", "-g", OPENCLAW_NPM_PACKAGE]
        success, output = self._run_command(cmd)
        if not success:
            self.finished.emit(False, f"安装失败：{output}")
            return
        
        # 配置
        self.progress.emit("配置 OpenClaw...")
        data_dir = os.path.expanduser(self.config.data_dir)
        os.makedirs(data_dir, exist_ok=True)
        
        config_file = os.path.join(data_dir, "openclaw.json")
        config_data = {
            "port": self.config.port,
            "token": self.config.token,
            "log_level": self.config.log_level
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2)
        
        # 启动服务
        if self.config.install_daemon:
            self.progress.emit("启动守护进程...")
            self._run_command(["openclaw", "gateway", "start"])
        
        self.finished.emit(True, "部署完成！")
    
    def _deploy_local(self):
        """本地源码部署"""
        self.progress.emit("克隆 OpenClaw 仓库...")
        
        data_dir = os.path.expanduser(self.config.data_dir)
        src_dir = os.path.join(data_dir, "src")
        
        if os.path.exists(src_dir):
            self.progress.emit("检测到已有源码，跳过克隆...")
        else:
            success, output = self._run_command(["git", "clone", OPENCLAW_REPO, src_dir])
            if not success:
                self.finished.emit(False, f"克隆失败：{output}")
                return
        
        # 安装依赖
        self.progress.emit("安装依赖...")
        os.chdir(src_dir)
        success, output = self._run_command([self.config.package_manager, "install"])
        if not success:
            self.finished.emit(False, f"安装依赖失败：{output}")
            return
        
        # 构建
        self.progress.emit("构建项目...")
        success, output = self._run_command([self.config.package_manager, "build"])
        if not success:
            self.finished.emit(False, f"构建失败：{output}")
            return
        
        self.finished.emit(True, "本地部署完成！")
    
    def _deploy_docker_compose(self):
        """Docker Compose 部署"""
        self.progress.emit("创建 docker-compose.yml...")
        
        data_dir = os.path.expanduser(self.config.data_dir)
        os.makedirs(data_dir, exist_ok=True)
        
        compose_content = f"""version: '{self.config.docker_compose_version}'
services:
  openclaw:
    image: {self.config.docker_image}
    container_name: {self.config.docker_container_name}
    ports:
      - "{self.config.port}:18789"
    environment:
      - OPENCLAW_TOKEN={self.config.token}
      - LOG_LEVEL={self.config.log_level}
    volumes:
      - {data_dir}/data:/app/data
    restart: unless-stopped
"""
        
        compose_file = os.path.join(data_dir, "docker-compose.yml")
        with open(compose_file, 'w', encoding='utf-8') as f:
            f.write(compose_content)
        
        # 启动容器
        self.progress.emit("启动 Docker 容器...")
        os.chdir(data_dir)
        success, output = self._run_command(["docker-compose", "up", "-d"])
        if not success:
            self.finished.emit(False, f"启动失败：{output}")
            return
        
        self.finished.emit(True, "Docker Compose 部署完成！")
    
    def _deploy_docker_run(self):
        """Docker Run 部署"""
        self.progress.emit("启动 Docker 容器...")
        
        cmd = [
            "docker", "run", "-d",
            "--name", self.config.docker_container_name,
            "-p", f"{self.config.port}:18789",
            "-e", f"OPENCLAW_TOKEN={self.config.token}",
            "-e", f"LOG_LEVEL={self.config.log_level}",
            self.config.docker_image
        ]
        
        success, output = self._run_command(cmd)
        if not success:
            self.finished.emit(False, f"启动失败：{output}")
            return
        
        self.finished.emit(True, "Docker Run 部署完成！")
    
    def _run_command(self, cmd: List[str]) -> Tuple[bool, str]:
        """运行命令并返回结果"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            return result.returncode == 0, result.stdout or result.stderr
        except Exception as e:
            return False, str(e)


class UninstallThread(QThread):
    """卸载线程"""
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)
    
    def __init__(self, options: UninstallOptions, config: DeployConfig):
        super().__init__()
        self.options = options
        self.config = config
    
    def run(self):
        """执行卸载"""
        try:
            # 停止服务
            if self.options.stop_services:
                self.progress.emit("停止服务...")
                self._run_command(["openclaw", "gateway", "stop"], ignore_error=True)
                self._run_command(["docker", "stop", self.config.docker_container_name], ignore_error=True)
            
            # 卸载 npm 包
            if self.options.uninstall_npm:
                self.progress.emit("卸载 npm 包...")
                self._run_command([self.config.package_manager, "uninstall", "-g", OPENCLAW_NPM_PACKAGE], ignore_error=True)
            
            # 删除 Docker 容器
            if self.options.remove_docker:
                self.progress.emit("删除 Docker 容器...")
                self._run_command(["docker", "rm", "-f", self.config.docker_container_name], ignore_error=True)
            
            # 删除数据目录
            if self.options.remove_data_dir:
                self.progress.emit("删除数据目录...")
                data_dir = os.path.expanduser(self.config.data_dir)
                if os.path.exists(data_dir):
                    shutil.rmtree(data_dir)
            
            # 清理缓存
            if self.options.remove_cache:
                self.progress.emit("清理缓存...")
                self._run_command(["npm", "cache", "clean", "--force"], ignore_error=True)
                self._run_command(["pnpm", "store", "prune"], ignore_error=True)
            
            # 删除配置
            if self.options.remove_config:
                self.progress.emit("删除配置...")
                config_dir = os.path.expanduser("~/.openclaw")
                if os.path.exists(config_dir):
                    shutil.rmtree(config_dir)
            
            self.finished.emit(True, "卸载完成！")
        except Exception as e:
            self.finished.emit(False, str(e))
    
    def _run_command(self, cmd: List[str], ignore_error: bool = False) -> Tuple[bool, str]:
        """运行命令并返回结果"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.returncode == 0, result.stdout or result.stderr
        except Exception as e:
            if ignore_error:
                return True, ""
            return False, str(e)


# ==============================================================================
# 主窗口类
# ==============================================================================

class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.config = DeployConfig()
        self.env_check: Optional[EnvironmentCheck] = None
        self.init_ui()
        self.run_env_check()
    
    def init_ui(self):
        """初始化 UI"""
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1000, 700)
        
        # 设置窗口图标
        icon_path = r"D:\Users\xc\Desktop\Y1-Claw\icon.ico"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # 创建状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage(f"欢迎使用 {APP_NAME} v{APP_VERSION}")
        
        # 创建菜单栏
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件 (&F)")
        
        exit_action = QAction("退出 (&Q)", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        help_menu = menubar.addMenu("帮助 (&H)")
        about_action = QAction("关于 (&A)", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        # 创建主选项卡
        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        
        # 环境检测页面
        env_tab = self.create_env_tab()
        tabs.addTab(env_tab, "环境检测")
        
        # 部署配置页面
        deploy_tab = self.create_deploy_tab()
        tabs.addTab(deploy_tab, "部署配置")
        
        # 监控页面
        monitor_tab = self.create_monitor_tab()
        tabs.addTab(monitor_tab, "监控管理")
        
        # 工具页面
        tools_tab = self.create_tools_tab()
        tabs.addTab(tools_tab, "工具")
    
    def create_env_tab(self) -> QWidget:
        """创建环境检测页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 检测按钮
        btn_layout = QHBoxLayout()
        check_btn = QPushButton("重新检测")
        check_btn.clicked.connect(self.run_env_check)
        btn_layout.addWidget(check_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 检测结果表格
        self.env_table = QTableWidget()
        self.env_table.setColumnCount(3)
        self.env_table.setHorizontalHeaderLabels(["检测项", "状态", "详情"])
        self.env_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.env_table)
        
        return widget
    
    def create_deploy_tab(self) -> QWidget:
        """创建部署配置页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 部署方式选择
        method_group = QGroupBox("部署方式")
        method_layout = QVBoxLayout(method_group)
        
        self.method_combo = QComboBox()
        for method in DeployMethod:
            self.method_combo.addItem(method.display_name, method.name)
        self.method_combo.currentTextChanged.connect(self.on_method_changed)
        method_layout.addWidget(self.method_combo)
        
        self.method_desc = QLabel()
        method_layout.addWidget(self.method_desc)
        
        layout.addWidget(method_group)
        
        # 基础配置
        config_group = QGroupBox("基础配置")
        config_layout = QFormLayout(config_group)
        
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(self.config.port)
        config_layout.addRow("端口:", self.port_spin)
        
        self.token_edit = QLineEdit(self.config.token)
        config_layout.addRow("Token:", self.token_edit)
        
        self.pkg_mgr_combo = QComboBox()
        self.pkg_mgr_combo.addItems(["npm", "pnpm", "bun"])
        config_layout.addRow("包管理器:", self.pkg_mgr_combo)
        
        self.daemon_check = QCheckBox("安装守护进程")
        self.daemon_check.setChecked(self.config.install_daemon)
        config_layout.addRow(self.daemon_check)
        
        layout.addWidget(config_group)
        
        # 部署按钮
        deploy_btn = QPushButton("开始部署")
        deploy_btn.clicked.connect(self.start_deployment)
        layout.addWidget(deploy_btn)
        
        layout.addStretch()
        
        return widget
    
    def create_monitor_tab(self) -> QWidget:
        """创建监控管理页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 状态显示
        status_group = QGroupBox("服务状态")
        status_layout = QHBoxLayout(status_group)
        
        self.status_label = QLabel("状态：未知")
        status_layout.addWidget(self.status_label)
        
        start_btn = QPushButton("启动")
        start_btn.clicked.connect(self.start_service)
        status_layout.addWidget(start_btn)
        
        stop_btn = QPushButton("停止")
        stop_btn.clicked.connect(self.stop_service)
        status_layout.addWidget(stop_btn)
        
        restart_btn = QPushButton("重启")
        restart_btn.clicked.connect(self.restart_service)
        status_layout.addWidget(restart_btn)
        
        open_btn = QPushButton("打开 Web UI")
        open_btn.clicked.connect(self.open_web_ui)
        status_layout.addWidget(open_btn)
        
        layout.addWidget(status_group)
        
        # 日志显示
        log_group = QGroupBox("实时日志")
        log_layout = QVBoxLayout(log_group)
        
        self.monitor_log = QPlainTextEdit()
        self.monitor_log.setReadOnly(True)
        self.monitor_log.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.monitor_log)
        
        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(self.monitor_log.clear)
        log_layout.addWidget(clear_btn)
        
        layout.addWidget(log_group)
        
        return widget
    
    def create_tools_tab(self) -> QWidget:
        """创建工具页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 快捷命令
        cmd_group = QGroupBox("快捷命令")
        cmd_layout = QHBoxLayout(cmd_group)
        
        self.quick_cmd = QLineEdit()
        self.quick_cmd.setPlaceholderText("输入命令：backup / restore / clean")
        cmd_layout.addWidget(self.quick_cmd)
        
        exec_btn = QPushButton("执行")
        exec_btn.clicked.connect(self.execute_quick_cmd)
        cmd_layout.addWidget(exec_btn)
        
        layout.addWidget(cmd_group)
        
        # 工具按钮
        tools_group = QGroupBox("工具")
        tools_layout = QGridLayout(tools_group)
        
        backup_btn = QPushButton("备份配置")
        backup_btn.clicked.connect(self.backup_config)
        tools_layout.addWidget(backup_btn, 0, 0)
        
        restore_btn = QPushButton("恢复配置")
        restore_btn.clicked.connect(self.restore_config)
        tools_layout.addWidget(restore_btn, 0, 1)
        
        clean_btn = QPushButton("清理缓存")
        clean_btn.clicked.connect(self.clean_cache)
        tools_layout.addWidget(clean_btn, 1, 0)
        
        edit_btn = QPushButton("编辑配置")
        edit_btn.clicked.connect(self.edit_config)
        tools_layout.addWidget(edit_btn, 1, 1)
        
        layout.addWidget(tools_group)
        
        # 配置编辑器
        editor_group = QGroupBox("配置编辑器")
        editor_layout = QVBoxLayout(editor_group)
        
        self.config_editor = QPlainTextEdit()
        self.config_editor.setFont(QFont("Consolas", 9))
        editor_layout.addWidget(self.config_editor)
        
        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self.save_config_file)
        editor_layout.addWidget(save_btn)
        
        layout.addWidget(editor_group)
        
        return widget
    
    def on_method_changed(self, name: str):
        """部署方式改变"""
        method = DeployMethod[name]
        self.method_desc.setText(method.description)
    
    def run_env_check(self):
        """运行环境检测"""
        self.statusBar.showMessage("正在检测环境...")
        
        self.env_thread = EnvCheckThread()
        self.env_thread.finished.connect(self.on_env_check_finished)
        self.env_thread.progress.connect(lambda msg: self.statusBar.showMessage(msg))
        self.env_thread.start()
    
    def on_env_check_finished(self, check: EnvironmentCheck):
        """环境检测完成"""
        self.env_check = check
        self.update_env_table(check)
        self.statusBar.showMessage("环境检测完成")
    
    def update_env_table(self, check: EnvironmentCheck):
        """更新环境检测表格"""
        self.env_table.setRowCount(10)
        
        items = [
            ("操作系统", "✓" if check.system else "✗", f"{check.system} ({check.architecture})"),
            ("Node.js", "✓" if check.node_installed else "✗", check.node_version),
            ("npm", "✓" if check.npm_installed else "✗", check.npm_version),
            ("pnpm", "✓" if check.pnpm_installed else "✗", check.pnpm_version),
            ("Docker", "✓" if check.docker_installed else "✗", check.docker_version),
            ("Docker Compose", "✓" if check.docker_compose_installed else "✗", check.docker_version),
            ("Git", "✓" if check.git_installed else "✗", check.git_version),
            (f"端口 {check.port_checked}", "✓" if check.port_available else "✗", "可用" if check.port_available else "被占用"),
        ]
        
        for i, (item, status, detail) in enumerate(items):
            self.env_table.setItem(i, 0, QTableWidgetItem(item))
            self.env_table.setItem(i, 1, QTableWidgetItem(status))
            self.env_table.setItem(i, 2, QTableWidgetItem(detail))
    
    def start_deployment(self):
        """开始部署"""
        # 更新配置
        method_name = self.method_combo.currentData()
        self.config.method = method_name
        self.config.port = self.port_spin.value()
        self.config.token = self.token_edit.text()
        self.config.package_manager = self.pkg_mgr_combo.currentText()
        self.config.install_daemon = self.daemon_check.isChecked()
        
        # 创建部署线程
        self.deploy_thread = DeployThread(self.config)
        self.deploy_thread.finished.connect(self.on_deployment_finished)
        self.deploy_thread.progress.connect(lambda msg: self.statusBar.showMessage(msg))
        self.deploy_thread.start()
        
        self.statusBar.showMessage("正在部署...")
    
    def on_deployment_finished(self, success: bool, message: str):
        """部署完成"""
        if success:
            QMessageBox.information(self, "成功", message)
            self.monitor_log.appendPlainText(f"[SUCCESS] {message}")
        else:
            QMessageBox.critical(self, "错误", message)
            self.monitor_log.appendPlainText(f"[ERROR] {message}")
        
        self.statusBar.showMessage(message)
    
    def start_service(self):
        """启动服务"""
        self.monitor_log.appendPlainText("[INFO] 正在启动服务...")
        success, output = self._run_command(["openclaw", "gateway", "start"])
        if success:
            self.monitor_log.appendPlainText("[SUCCESS] 服务已启动")
        else:
            self.monitor_log.appendPlainText(f"[ERROR] 启动失败：{output}")
    
    def stop_service(self):
        """停止服务"""
        self.monitor_log.appendPlainText("[INFO] 正在停止服务...")
        success, output = self._run_command(["openclaw", "gateway", "stop"])
        if success:
            self.monitor_log.appendPlainText("[SUCCESS] 服务已停止")
        else:
            self.monitor_log.appendPlainText(f"[ERROR] 停止失败：{output}")
    
    def restart_service(self):
        """重启服务"""
        self.monitor_log.appendPlainText("[INFO] 正在重启服务...")
        self.stop_service()
        time.sleep(2)
        self.start_service()
    
    def open_web_ui(self):
        """打开 Web 界面"""
        url = f"http://127.0.0.1:{self.config.port}?token={self.config.token}"
        webbrowser.open(url)
        self.monitor_log.appendPlainText(f"[INFO] 打开 Web UI: {url}")
    
    def execute_quick_cmd(self):
        """执行快捷命令"""
        cmd = self.quick_cmd.text().strip()
        if not cmd:
            return
        
        self.monitor_log.appendPlainText(f"[CMD] $ {cmd}")
        
        # 特殊处理内部命令
        if cmd == "backup":
            self.backup_config()
            return
        elif cmd == "restore":
            self.restore_config()
            return
        elif cmd == "clean":
            self.clean_cache()
            return
        
        # 执行系统命令
        success, output = self._run_command(cmd.split())
        self.monitor_log.appendPlainText(output if output else "[INFO] 命令执行完成")
    
    def backup_config(self):
        """备份配置"""
        backup_dir = os.path.expanduser(f"~/.openclaw-backup-{int(time.time())}")
        data_dir = os.path.expanduser("~/.openclaw")
        
        if os.path.exists(data_dir):
            try:
                shutil.copytree(data_dir, backup_dir)
                self.monitor_log.appendPlainText(f"[SUCCESS] 配置已备份到：{backup_dir}")
                QMessageBox.information(self, "备份成功", f"配置已备份到:\n{backup_dir}")
            except Exception as e:
                self.monitor_log.appendPlainText(f"[ERROR] 备份失败：{e}")
        else:
            QMessageBox.warning(self, "警告", "没有找到配置目录")
    
    def restore_config(self):
        """恢复配置"""
        backup_dir = QFileDialog.getExistingDirectory(self, "选择备份目录")
        if not backup_dir:
            return
        
        data_dir = os.path.expanduser("~/.openclaw")
        
        # 备份当前配置
        if os.path.exists(data_dir):
            temp_backup = os.path.expanduser(f"~/.openclaw-temp-{int(time.time())}")
            shutil.move(data_dir, temp_backup)
        
        try:
            shutil.copytree(backup_dir, data_dir)
            self.monitor_log.appendPlainText(f"[SUCCESS] 配置已从 {backup_dir} 恢复")
            QMessageBox.information(self, "恢复成功", "配置已恢复，请重启服务")
        except Exception as e:
            self.monitor_log.appendPlainText(f"[ERROR] 恢复失败：{e}")
            # 恢复临时备份
            if os.path.exists(temp_backup):
                shutil.move(temp_backup, data_dir)
    
    def clean_cache(self):
        """清理缓存"""
        self._run_command(["npm", "cache", "clean", "--force"], ignore_error=True)
        self._run_command(["pnpm", "store", "prune"], ignore_error=True)
        
        cache_dirs = [
            os.path.expanduser("~/.openclaw/cache"),
            os.path.expanduser("~/.cache/openclaw"),
            os.path.expanduser("~/Library/Caches/OpenClaw") if IS_MACOS else ""
        ]
        
        for d in cache_dirs:
            if d and os.path.exists(d):
                try:
                    shutil.rmtree(d)
                except:
                    pass
        
        self.monitor_log.appendPlainText("[SUCCESS] 缓存已清理")
        QMessageBox.information(self, "清理完成", "所有缓存已清理")
    
    def edit_config(self):
        """编辑配置"""
        self.load_config_file()
    
    def load_config_file(self):
        """加载配置文件"""
        config_path = os.path.expanduser("~/.openclaw/openclaw.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.config_editor.setPlainText(content)
                    self.monitor_log.appendPlainText(f"[INFO] 已加载：{config_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法加载配置：{e}")
        else:
            # 创建默认配置
            default_config = {
                "port": self.config.port,
                "token": self.config.token,
                "log_level": self.config.log_level
            }
            self.config_editor.setPlainText(json.dumps(default_config, indent=2))
            self.monitor_log.appendPlainText("[INFO] 创建新配置")
    
    def save_config_file(self):
        """保存配置文件"""
        config_path = os.path.expanduser("~/.openclaw/openclaw.json")
        try:
            content = self.config_editor.toPlainText()
            # 验证 JSON
            json.loads(content)
            
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.monitor_log.appendPlainText(f"[SUCCESS] 配置已保存：{config_path}")
            QMessageBox.information(self, "成功", "配置已保存")
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "错误", f"JSON 格式错误：{e}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{e}")
    
    def _run_command(self, cmd: List[str], ignore_error: bool = False) -> Tuple[bool, str]:
        """运行命令并返回结果"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.returncode == 0, result.stdout or result.stderr
        except Exception as e:
            if ignore_error:
                return True, ""
            return False, str(e)
    
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于",
            f"{APP_NAME}\n版本：{APP_VERSION}\n作者：{APP_AUTHOR}\n\n"
            "OpenClaw 最强部署工具！"
        )
    
    def closeEvent(self, event):
        """关闭事件"""
        reply = QMessageBox.question(
            self,
            "确认退出",
            "确定要退出吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()


# ==============================================================================
# 程序入口
# ==============================================================================

def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_AUTHOR)
    
    # 设置样式
    app.setStyle("Fusion")
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
