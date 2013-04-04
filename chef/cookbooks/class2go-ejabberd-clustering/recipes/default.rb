directory "/var/lib/ejabberd" do
    owner "ejabberd"
    group "ejabberd"
    mode 00700
    action :create
end

execute "ejabberd clustering info" do
    user 'root'
    cwd node['system']['admin_home'] + "class2go/main"
    command "python manage.py aws_getinfo -e /var/lib/ejabberd/.hosts.erlang -C"
end

file "/var/lib/ejabberd/.hosts.erlang" do
    mode 00640
    owner 'ejabberd'
    group 'ejabberd'
    action :touch
end

