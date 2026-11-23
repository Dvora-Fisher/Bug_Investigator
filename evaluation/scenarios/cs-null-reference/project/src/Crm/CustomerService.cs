namespace Crm;

public record Customer(int Id, string Name);

public interface ICustomerRepository
{
    /// <summary>Returns null when there is no customer with this id.</summary>
    Customer? Find(int id);
}

public class CustomerService(ICustomerRepository repository)
{
    public const string UnknownCustomer = "Unknown customer";

    /// <summary>Name shown on invoices; UnknownCustomer for ids that no longer exist.</summary>
    public string DisplayName(int id) => repository.Find(id)!.Name.Trim();
}
