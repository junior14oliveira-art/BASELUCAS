"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { SortableContext, useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { bl } from "@/lib/baselinker/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import type { BLPickPackCart, BLOrder } from "@/lib/baselinker/types";
import { Plus, Trash2, Package, GripVertical, X, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { formatDate, formatCurrency } from "@/lib/utils";

interface CartWithOrders extends BLPickPackCart {
  orderIds: number[];
  orders: BLOrder[];
}

export default function PickPackPage() {
  const qc = useQueryClient();
  const [newCartName, setNewCartName] = useState("");
  const [activeOrder, setActiveOrder] = useState<BLOrder | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

  const { data: cartsRes, isLoading: cartsLoading } = useQuery({
    queryKey: ["pickpack-carts"],
    queryFn: () => bl.getPickPackCarts(),
    staleTime: 30_000,
  });
  const carts: BLPickPackCart[] = (cartsRes as { carts?: BLPickPackCart[] })?.carts ?? [];

  const { data: ordersRes, isLoading: ordersLoading } = useQuery({
    queryKey: ["orders-pickpack"],
    queryFn: () =>
      bl.getOrders({
        date_confirmed_from: Math.floor(Date.now() / 1000) - 7 * 86400,
        get_unconfirmed_orders: false,
      }),
    staleTime: 20_000,
  });
  const allOrders: BLOrder[] = (ordersRes as { orders?: BLOrder[] })?.orders ?? [];

  // Queries per cart — top-level, stable count avoids hook rules issues
  const c0 = useQuery({ queryKey: ["pp-cart", carts[0]?.cart_id], queryFn: () => bl.getPickPackCartOrders(carts[0].cart_id), enabled: !!carts[0] });
  const c1 = useQuery({ queryKey: ["pp-cart", carts[1]?.cart_id], queryFn: () => bl.getPickPackCartOrders(carts[1].cart_id), enabled: !!carts[1] });
  const c2 = useQuery({ queryKey: ["pp-cart", carts[2]?.cart_id], queryFn: () => bl.getPickPackCartOrders(carts[2].cart_id), enabled: !!carts[2] });
  const c3 = useQuery({ queryKey: ["pp-cart", carts[3]?.cart_id], queryFn: () => bl.getPickPackCartOrders(carts[3].cart_id), enabled: !!carts[3] });
  const c4 = useQuery({ queryKey: ["pp-cart", carts[4]?.cart_id], queryFn: () => bl.getPickPackCartOrders(carts[4].cart_id), enabled: !!carts[4] });
  const c5 = useQuery({ queryKey: ["pp-cart", carts[5]?.cart_id], queryFn: () => bl.getPickPackCartOrders(carts[5].cart_id), enabled: !!carts[5] });
  const cartDataList = [c0, c1, c2, c3, c4, c5];

  const cartsWithOrders: CartWithOrders[] = carts.slice(0, 6).map((cart, i) => {
    const orderIds: number[] = (cartDataList[i]?.data as { orders?: number[] })?.orders ?? [];
    const orders = orderIds.map((id) => allOrders.find((o) => o.order_id === id)).filter(Boolean) as BLOrder[];
    return { ...cart, orderIds, orders };
  });

  const assignedIds = new Set(cartsWithOrders.flatMap((c) => c.orderIds));
  const unassignedOrders = allOrders.filter((o) => !assignedIds.has(o.order_id));

  const createCartMut = useMutation({
    mutationFn: (name: string) => bl.addPickPackCart(name),
    onSuccess: () => { toast.success("Fila criada"); setNewCartName(""); qc.invalidateQueries({ queryKey: ["pickpack-carts"] }); },
    onError: () => toast.error("Erro ao criar fila"),
  });

  const deleteCartMut = useMutation({
    mutationFn: (cartId: number) => bl.deletePickPackCart(cartId),
    onSuccess: () => { toast.success("Fila removida"); qc.invalidateQueries({ queryKey: ["pickpack-carts"] }); },
  });

  const assignMut = useMutation({
    mutationFn: ({ cartId, orderIds }: { cartId: number; orderIds: number[] }) =>
      bl.addPickPackOrdersToCart(cartId, orderIds),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pp-cart"] });
      qc.invalidateQueries({ queryKey: ["orders-pickpack"] });
    },
    onError: () => toast.error("Erro ao mover pedido"),
  });

  const removeFromCartMut = useMutation({
    mutationFn: (orderId: number) => bl.deletePickPackOrderFromCart(orderId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pp-cart"] });
      qc.invalidateQueries({ queryKey: ["orders-pickpack"] });
    },
  });

  function handleDragStart(event: DragStartEvent) {
    const orderId = event.active.id as number;
    setActiveOrder(allOrders.find((o) => o.order_id === orderId) ?? null);
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    setActiveOrder(null);
    if (!over) return;
    const orderId = active.id as number;
    const cartId = over.id as number;
    if (cartId < 0) return; // unassigned column
    const targetCart = cartsWithOrders.find((c) => c.cart_id === cartId);
    if (targetCart?.orderIds.includes(orderId)) return;
    assignMut.mutate({ cartId, orderIds: [orderId] });
  }

  return (
    <div className="p-4 md:p-6 space-y-5 h-full">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-base font-semibold">Filas PickPack</h1>
          <p className="text-xs text-muted-foreground">Organize pedidos em filas de separação e embalagem</p>
        </div>
        <div className="flex items-center gap-2">
          <Input
            placeholder="Nome da nova fila..."
            value={newCartName}
            onChange={(e) => setNewCartName(e.target.value)}
            className="h-8 w-44 text-sm"
            onKeyDown={(e) => { if (e.key === "Enter" && newCartName.trim()) createCartMut.mutate(newCartName.trim()); }}
            aria-label="Nome da nova fila"
          />
          <Button size="sm" onClick={() => { if (newCartName.trim()) createCartMut.mutate(newCartName.trim()); }} disabled={!newCartName.trim() || createCartMut.isPending}>
            <Plus className="h-3.5 w-3.5" /> Criar Fila
          </Button>
          <Button variant="outline" size="icon" onClick={() => qc.invalidateQueries({ queryKey: ["pickpack-carts"] })} aria-label="Recarregar">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
        <div className="flex gap-4 overflow-x-auto pb-4" role="region" aria-label="Quadro Kanban PickPack">
          {/* Unassigned column */}
          <UnassignedColumn orders={unassignedOrders} loading={ordersLoading} />

          {/* Cart columns */}
          {cartsLoading
            ? Array.from({ length: 2 }).map((_, i) => (
                <div key={i} className="w-72 shrink-0">
                  <Skeleton className="h-8 w-full mb-3 rounded-lg" />
                  {Array.from({ length: 3 }).map((_, j) => <Skeleton key={j} className="h-20 w-full mb-2 rounded-lg" />)}
                </div>
              ))
            : cartsWithOrders.map((cart) => (
                <CartColumn
                  key={cart.cart_id}
                  cart={cart}
                  onDelete={() => deleteCartMut.mutate(cart.cart_id)}
                  onRemoveOrder={(orderId) => removeFromCartMut.mutate(orderId)}
                />
              ))}
        </div>

        <DragOverlay>
          {activeOrder && <OrderCard order={activeOrder} dragging />}
        </DragOverlay>
      </DndContext>
    </div>
  );
}

// ─── Unassigned column (not droppable) ───────────────────────────────────────

function UnassignedColumn({ orders, loading }: { orders: BLOrder[]; loading: boolean }) {
  return (
    <div className="w-72 shrink-0 flex flex-col rounded-lg border border-border bg-card" role="region" aria-label="Sem Fila">
      <div className="flex items-center justify-between px-3 py-2.5 border-b">
        <div>
          <h3 className="text-sm font-medium">Sem Fila</h3>
          <p className="text-xs text-muted-foreground">{orders.length} pedidos</p>
        </div>
      </div>
      <div className="flex-1 p-2 space-y-2 min-h-32 max-h-[calc(100vh-250px)] overflow-y-auto">
        {loading ? (
          Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-20 w-full rounded-lg" />)
        ) : orders.length === 0 ? (
          <div className="flex items-center justify-center h-24 text-xs text-muted-foreground border-2 border-dashed rounded-lg">
            Todos os pedidos estão em filas
          </div>
        ) : (
          orders.map((order) => <OrderCard key={order.order_id} order={order} />)
        )}
      </div>
    </div>
  );
}

// ─── Cart column (droppable) ──────────────────────────────────────────────────

function CartColumn({ cart, onDelete, onRemoveOrder }: {
  cart: CartWithOrders;
  onDelete: () => void;
  onRemoveOrder: (orderId: number) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: cart.cart_id });

  return (
    <div
      ref={setNodeRef}
      className={`w-72 shrink-0 flex flex-col rounded-lg border transition-colors ${isOver ? "border-primary bg-primary/5" : "border-border bg-card"}`}
      role="region"
      aria-label={`Fila: ${cart.name}`}
    >
      <div
        className="flex items-center justify-between px-3 py-2.5 border-b rounded-t-lg"
        style={{ borderTopColor: cart.color, borderTopWidth: 3 }}
      >
        <div>
          <h3 className="text-sm font-medium">{cart.name}</h3>
          <p className="text-xs text-muted-foreground">{cart.orders.length} pedidos</p>
        </div>
        <Button variant="ghost" size="icon-sm" onClick={onDelete}
          className="text-muted-foreground hover:text-destructive" aria-label={`Excluir fila ${cart.name}`}>
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
      <div className="flex-1 p-2 space-y-2 min-h-32 max-h-[calc(100vh-250px)] overflow-y-auto">
        {cart.orders.length === 0 ? (
          <div className="flex items-center justify-center h-24 text-xs text-muted-foreground border-2 border-dashed rounded-lg">
            Arraste pedidos aqui
          </div>
        ) : (
          <SortableContext items={cart.orders.map((o) => o.order_id)}>
            {cart.orders.map((order) => (
              <SortableOrderCard
                key={order.order_id}
                order={order}
                onRemove={() => onRemoveOrder(order.order_id)}
              />
            ))}
          </SortableContext>
        )}
      </div>
    </div>
  );
}

// ─── Sortable card wrapper ────────────────────────────────────────────────────

function SortableOrderCard({ order, onRemove }: { order: BLOrder; onRemove: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: order.order_id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.4 : 1 };
  return (
    <div ref={setNodeRef} style={style} {...attributes}>
      <OrderCard order={order} onRemove={onRemove} dragHandleProps={listeners} />
    </div>
  );
}

// ─── Order card ───────────────────────────────────────────────────────────────

function OrderCard({ order, onRemove, dragging, dragHandleProps }: {
  order: BLOrder;
  onRemove?: () => void;
  dragging?: boolean;
  dragHandleProps?: Record<string, unknown>;
}) {
  const total = (order.products ?? []).reduce((s, p) => s + p.price_brutto * p.quantity, 0);
  return (
    <div
      className={`rounded-lg border bg-background p-2.5 shadow-sm hover:shadow-md transition-shadow ${dragging ? "shadow-xl ring-2 ring-primary rotate-1" : ""}`}
      role="article"
      aria-label={`Pedido #${order.order_id}`}
    >
      <div className="flex items-start justify-between gap-1">
        <div className="flex items-center gap-1.5 min-w-0">
          {dragHandleProps && (
            <button {...dragHandleProps}
              className="cursor-grab active:cursor-grabbing text-muted-foreground hover:text-foreground shrink-0 touch-none"
              aria-label="Arrastar pedido">
              <GripVertical className="h-4 w-4" />
            </button>
          )}
          <div className="min-w-0">
            <p className="text-sm font-semibold text-primary">#{order.order_id}</p>
            <p className="text-xs text-muted-foreground truncate">{order.delivery_fullname || order.email || "—"}</p>
          </div>
        </div>
        {onRemove && (
          <button onClick={onRemove} className="text-muted-foreground hover:text-destructive transition-colors shrink-0" aria-label="Remover da fila">
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      <div className="mt-2 flex items-center justify-between text-xs">
        <span className="flex items-center gap-1 text-muted-foreground">
          <Package className="h-3 w-3" />{order.products?.length ?? 0} item(ns)
        </span>
        <span className="font-medium tabular-nums">{formatCurrency(total, order.currency)}</span>
      </div>
      <p className="mt-1 text-[10px] text-muted-foreground">
        {formatDate(order.date_confirmed || order.date_add, "dd/MM HH:mm")}
      </p>
    </div>
  );
}
