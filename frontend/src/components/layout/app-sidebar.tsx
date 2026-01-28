"use client";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  {
    title: "Dashboard",
    href: "/",
    icon: "📊",
  },
  {
    title: "Projects",
    href: "/projects",
    icon: "📁",
  },
  {
    title: "Tasks",
    href: "/tasks",
    icon: "✅",
  },
  {
    title: "Workflow",
    href: "/workflow",
    icon: "🔄",
  },
  {
    title: "Settings",
    href: "/settings",
    icon: "⚙️",
  },
];

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <Sidebar>
      <SidebarHeader>
        <div className="flex items-center gap-2 px-4 py-2">
          <span className="text-xl font-bold">Ralph</span>
          <span className="text-sm text-muted-foreground">Orchestrator</span>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton asChild isActive={pathname === item.href}>
                    <Link href={item.href}>
                      <span>{item.icon}</span>
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <div className="px-4 py-2 text-xs text-muted-foreground">
          Ralph Orchestrator v0.1.0
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
