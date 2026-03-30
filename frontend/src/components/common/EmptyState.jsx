function EmptyState({ icon, title, description, action, onAction }) {
  return (
    <div className="text-center py-12">
      <div className="text-6xl mb-4">{icon}</div>
      <h3 className="text-lg font-medium text-gray-900 mb-2">{title}</h3>
      <p className="text-gray-500 mb-6 max-w-md mx-auto">{description}</p>
      {action && (
        <button className="btn-primary" onClick={onAction}>
          {action}
        </button>
      )}
    </div>
  );
}

export default EmptyState;
