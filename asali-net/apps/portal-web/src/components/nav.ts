import { Boxes, ClipboardList, FileText, History, Network as NetworkIcon, PackageCheck, Pill, Search, ShieldAlert, ShoppingCart, Truck, Undo2, Warehouse } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { OrgType } from '../api/types'

export interface NavItem { to: string; label: string; icon: LucideIcon }

// What each kind of organisation can do, most used first (DESIGN.md 5.2). At most 7 items.
export const NAV: Record<OrgType, NavItem[]> = {
  pharma: [
    { to: '/dispatch', label: 'Dispatch', icon: Truck }, { to: '/batches', label: 'Batches', icon: Boxes }, { to: '/products', label: 'Products', icon: Pill },
    { to: '/recalls', label: 'Recalls', icon: ShieldAlert }, { to: '/documents', label: 'Documents', icon: FileText }, { to: '/activity', label: 'Activity', icon: History }, { to: '/network', label: 'Network', icon: NetworkIcon },
  ],
  distributor: [
    { to: '/receive', label: 'Receive', icon: PackageCheck }, { to: '/dispatch', label: 'Dispatch', icon: Truck }, { to: '/stock', label: 'Stock', icon: Warehouse },
    { to: '/documents', label: 'Documents', icon: FileText }, { to: '/activity', label: 'Activity', icon: History }, { to: '/network', label: 'Network', icon: NetworkIcon },
  ],
  shop: [
    { to: '/sell', label: 'Sell', icon: ShoppingCart }, { to: '/receive', label: 'Receive', icon: PackageCheck }, { to: '/stock', label: 'Stock', icon: Warehouse },
    { to: '/returns', label: 'Returns', icon: Undo2 }, { to: '/alerts', label: 'Alerts', icon: ShieldAlert }, { to: '/documents', label: 'Documents', icon: FileText }, { to: '/network', label: 'Network', icon: NetworkIcon },
  ],
  regulator: [
    { to: '/investigate', label: 'Investigate', icon: Search }, { to: '/complaints', label: 'Complaints', icon: ClipboardList }, { to: '/alerts', label: 'Alerts', icon: ShieldAlert },
    { to: '/licences', label: 'Licences', icon: FileText }, { to: '/documents', label: 'Documents', icon: FileText }, { to: '/network', label: 'Network', icon: NetworkIcon },
  ],
  consumer: [],
}

