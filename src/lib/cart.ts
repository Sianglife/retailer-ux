import { products } from "../data/products.ts";

export interface CartItem {
	id: string;
	count: number;
	one_price: number;
}

interface Quantity {
	id: string;
	count: number;
}

export interface Cart {
	total: number;
	items: CartItem[];
}

function readStorage(key: string): unknown {
	const value = localStorage.getItem(key);
	try {
		return value ? JSON.parse(value) : null;
	} catch {
		return null;
	}
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null;
}

export function getCart(): Cart {
	const saved = readStorage("cart");
	const items: CartItem[] = [];
	if (isRecord(saved) && Array.isArray(saved.items)) {
		for (const item of saved.items) {
			if (!isRecord(item)) continue;
			const product = products.find(product => product.id === item.id);
			if (!product || !Number.isSafeInteger(item.count) || Number(item.count) <= 0) continue;
			if (items.some(existing => existing.id === product.id)) continue;
			items.push({
				id: product.id,
				count: Number(item.count),
				one_price: typeof item.one_price === "number" && Number.isFinite(item.one_price) && item.one_price >= 0 ? item.one_price : product.price
			});
		}
	}
	return { items, total: items.reduce((total, item) => total + item.count * item.one_price, 0) };
}

export function getQuantity(): Quantity[] {
	const saved = readStorage("quantity");
	const cart = getCart();
	return products.map(product => {
		const item = Array.isArray(saved) ? saved.find(item => isRecord(item) && item.id === product.id) : null;
		const reserved = cart.items.find(item => item.id === product.id)?.count ?? 0;
		return {
			id: product.id,
			count: item && Number.isSafeInteger(item.count) && item.count >= 0 ? item.count : Math.max(0, product.stock - reserved)
		};
	});
}

export function initializeCart() {
	const cart = getCart();
	const quantity = getQuantity();
	localStorage.setItem("quantity", JSON.stringify(quantity));
	localStorage.setItem("cart", JSON.stringify(cart));
}

export function setCartCount(id: string, count: number) {
	if (!Number.isSafeInteger(count) || count < 0) {
		throw new Error("Enter a whole number of 0 or more.");
	}

	const product = products.find(product => product.id === id);
	if (!product) throw new Error("This product is no longer available.");

	const cart = getCart();
	const quantity = getQuantity();
	const stock = quantity.find(item => item.id === id)!;
	const index = cart.items.findIndex(item => item.id === id);
	const existing = cart.items[index];
	const difference = count - (existing?.count ?? 0);
	if (difference > stock.count) throw new Error("Not enough quantity in stock!");

	stock.count -= difference;
	if (count === 0) cart.items = cart.items.filter(item => item.id !== id);
	else if (existing) existing.count = count;
	else cart.items.push({ id, count, one_price: product.price });
	cart.total = cart.items.reduce((total, item) => total + item.count * item.one_price, 0);

	const previousQuantity = localStorage.getItem("quantity");
	localStorage.setItem("quantity", JSON.stringify(quantity));
	try {
		localStorage.setItem("cart", JSON.stringify(cart));
	} catch (error) {
		// Restore stock if saving the cart fails (for example, when storage is full).
		if (previousQuantity === null) localStorage.removeItem("quantity");
		else localStorage.setItem("quantity", previousQuantity);
		throw error;
	}
	window.dispatchEvent(new Event("cart-updated"));
}

export function addToCart(id: string) {
	const count = getCart().items.find(item => item.id === id)?.count ?? 0;
	setCartCount(id, count + 1);
}
