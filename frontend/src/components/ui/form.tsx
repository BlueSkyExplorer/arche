"use client";
import * as React from "react";
import * as LabelPrimitive from "@radix-ui/react-label";
import { Slot } from "@radix-ui/react-slot";
import { Controller, FormProvider, useFormContext, useFormState, type ControllerProps, type FieldPath, type FieldValues } from "react-hook-form";
import { cn } from "@/lib/utils";
import { Label } from "@/components/ui/label";

export const Form = FormProvider;
type FormFieldContextValue<T extends FieldValues = FieldValues, N extends FieldPath<T> = FieldPath<T>> = { name: N };
const FormFieldContext = React.createContext<FormFieldContextValue>({} as FormFieldContextValue);
export function FormField<T extends FieldValues, N extends FieldPath<T>>(props: ControllerProps<T, N>) { return <FormFieldContext.Provider value={{ name: props.name }}><Controller {...props} /></FormFieldContext.Provider>; }
const FormItemContext = React.createContext({ id: "" });
function useFormField() { const field = React.useContext(FormFieldContext); const item = React.useContext(FormItemContext); const { getFieldState } = useFormContext(); const state = useFormState({ name: field.name }); const fieldState = getFieldState(field.name, state); return { ...fieldState, formItemId: `${item.id}-form-item`, formDescriptionId: `${item.id}-form-item-description`, formMessageId: `${item.id}-form-item-message` }; }
export function FormItem({ className, ...props }: React.ComponentProps<"div">) { const id = React.useId(); return <FormItemContext.Provider value={{ id }}><div data-slot="form-item" className={cn("grid gap-2", className)} {...props} /></FormItemContext.Provider>; }
export function FormLabel({ className, ...props }: React.ComponentProps<typeof LabelPrimitive.Root>) { const { error, formItemId } = useFormField(); return <Label htmlFor={formItemId} className={cn(error && "text-destructive", className)} {...props} />; }
export function FormControl(props: React.ComponentProps<typeof Slot>) { const { error, formItemId, formDescriptionId, formMessageId } = useFormField(); return <Slot id={formItemId} aria-describedby={!error ? formDescriptionId : `${formDescriptionId} ${formMessageId}`} aria-invalid={!!error} {...props} />; }
export function FormDescription({ className, ...props }: React.ComponentProps<"p">) { const { formDescriptionId } = useFormField(); return <p id={formDescriptionId} className={cn("text-sm text-muted-foreground", className)} {...props} />; }
export function FormMessage({ className, children, ...props }: React.ComponentProps<"p">) { const { error, formMessageId } = useFormField(); const body = error ? String(error.message ?? "") : children; if (!body) return null; return <p id={formMessageId} className={cn("text-sm text-destructive", className)} {...props}>{body}</p>; }
