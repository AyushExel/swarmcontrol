const ROLE = { viewer: ['read'], editor: ['read', 'write'], admin: ['read', 'write', 'delete'] };

/**
 * May `user` perform `action` on `resource`? Roles grant actions; the owner of
 * a resource may also write it. Locked resources allow only reads, except for
 * admins. Unknown roles get nothing.
 */
export function can(user, action, resource) {
  if (resource.ownerId === user.id) return true;
  if (resource.locked && action !== 'read') return false;
  return (ROLE[user.role] ?? ROLE.viewer).includes(action);
}
