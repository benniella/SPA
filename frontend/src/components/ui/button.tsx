import Link from "next/link";
import type {
  AnchorHTMLAttributes,
  ButtonHTMLAttributes,
  MouseEvent as ReactMouseEvent,
  MouseEventHandler,
  ReactNode,
} from "react";
import { Children, cloneElement, isValidElement } from "react";

import { ButtonArrow } from "@/components/ui/icon";

export type ButtonVariant = "primary" | "technical" | "ai";
export type ButtonSize = "sm" | "md" | "lg";
export type ButtonIconPosition = "leading" | "trailing";

interface ButtonBaseProps {
  readonly variant?: ButtonVariant;
  readonly size?: ButtonSize;
  readonly block?: boolean;
  readonly fullWidth?: boolean;
  readonly arrow?: boolean;
  readonly icon?: ReactNode;
  readonly iconPosition?: ButtonIconPosition;
  readonly loading?: boolean;
  readonly loadingLabel?: string;
  readonly asChild?: boolean;
  readonly children: ReactNode;
  readonly className?: string;
}

type NativeButtonProps = Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  "children" | "className" | "disabled"
>;

export type ButtonProps = ButtonBaseProps &
  NativeButtonProps & {
    readonly disabled?: boolean;
  };

interface ButtonLinkBaseProps {
  readonly href: string;
  readonly variant?: ButtonVariant;
  readonly size?: ButtonSize;
  readonly block?: boolean;
  readonly fullWidth?: boolean;
  readonly arrow?: boolean;
  readonly icon?: ReactNode;
  readonly iconPosition?: ButtonIconPosition;
  readonly loading?: boolean;
  readonly loadingLabel?: string;
  readonly className?: string;
  readonly children: ReactNode;
}

export type ButtonLinkProps = ButtonLinkBaseProps &
  Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href" | "children" | "className">;

const FOCUSABLE_WHEN_DISABLED = "aria-disabled";

export function buttonClasses({
  variant = "primary",
  size = "md",
  block = false,
  fullWidth = false,
  loading = false,
  className,
}: {
  variant?: ButtonVariant;
  size?: ButtonSize;
  block?: boolean;
  fullWidth?: boolean;
  loading?: boolean;
  className?: string;
}): string {
  return [
    "spa-button",
    `spa-button--${variant}`,
    `spa-button--${size}`,
    block || fullWidth ? "spa-button--block" : null,
    loading ? "spa-button--loading" : null,
    className,
  ]
    .filter(Boolean)
    .join(" ");
}

function ButtonContents({
  children,
  arrow,
  icon,
  iconPosition = "leading",
  loading = false,
  loadingLabel,
}: {
  children: ReactNode;
  arrow: boolean;
  icon?: ReactNode;
  iconPosition?: ButtonIconPosition;
  loading?: boolean;
  loadingLabel?: string;
}) {
  const indicator = loading ? (
    <span className="spa-button__spinner" aria-hidden="true" />
  ) : arrow ? (
    <span className="spa-button__arrow">
      <ButtonArrow />
    </span>
  ) : null;

  return (
    <span className="spa-button__content">
      {icon && iconPosition === "leading" ? <span className="spa-button__icon">{icon}</span> : null}
      <span className="spa-button__label">{children}</span>
      {icon && iconPosition === "trailing" && !loading ? (
        <span className="spa-button__icon">{icon}</span>
      ) : null}
      {indicator}
      {loading ? <span className="visually-hidden">{loadingLabel ?? "Working"}</span> : null}
    </span>
  );
}

export function Button({
  variant = "primary",
  size = "md",
  block = false,
  fullWidth = false,
  arrow = true,
  icon,
  iconPosition = "leading",
  loading = false,
  loadingLabel,
  asChild = false,
  children,
  className,
  disabled = false,
  onClick,
  type = "button",
  ...rest
}: ButtonProps) {
  const classes = buttonClasses({ variant, size, block, fullWidth, loading, className });
  const inert = disabled || loading;

  const handleClick: MouseEventHandler<HTMLButtonElement> = (event) => {
    if (inert) {
      event.preventDefault();
      return;
    }
    onClick?.(event);
  };

  if (asChild) {
    const child = Children.only(children);

    if (!isValidElement<{ className?: string; children?: ReactNode }>(child)) {
      throw new Error("Button 'asChild' requires a single valid React element.");
    }

    return cloneElement(
      child,
      {
        className: [classes, child.props.className].filter(Boolean).join(" "),
        ...(inert ? { [FOCUSABLE_WHEN_DISABLED]: true } : {}),
        ...rest,
      },
      child.props.children,
    );
  }

  return (
    <button
      {...rest}
      type={type}
      className={classes}
      onClick={handleClick}
      disabled={disabled}
      {...(loading ? { "aria-busy": true } : {})}
      {...(inert ? { [FOCUSABLE_WHEN_DISABLED]: true } : {})}
    >
      <ButtonContents
        arrow={arrow}
        icon={icon}
        iconPosition={iconPosition}
        loading={loading}
        loadingLabel={loadingLabel}
      >
        {children}
      </ButtonContents>
    </button>
  );
}

export function ButtonLink({
  href,
  variant = "primary",
  size = "md",
  block = false,
  fullWidth = false,
  arrow = true,
  icon,
  iconPosition = "leading",
  loading = false,
  loadingLabel,
  className,
  children,
  ...rest
}: ButtonLinkProps) {
  const classes = buttonClasses({ variant, size, block, fullWidth, loading, className });
  const isExternal = /^https?:\/\//.test(href) || href.startsWith("//");
  const isInPageAnchor = href.startsWith("#");

  const contents = (
    <ButtonContents
      arrow={arrow}
      icon={icon}
      iconPosition={iconPosition}
      loading={loading}
      loadingLabel={loadingLabel}
    >
      {children}
    </ButtonContents>
  );

  const clickGuard = loading
    ? {
        onClick: (event: ReactMouseEvent<HTMLAnchorElement>) => event.preventDefault(),
      }
    : {};

  const linkProps = {
    ...rest,
    className: classes,
    ...clickGuard,
    ...(loading ? { "aria-busy": true, "aria-disabled": true } : {}),
  };

  if (isExternal || isInPageAnchor) {
    return (
      <a {...linkProps} href={href} {...(isExternal ? { rel: "noreferrer noopener" } : {})}>
        {contents}
      </a>
    );
  }

  return (
    <Link {...linkProps} href={href}>
      {contents}
    </Link>
  );
}
